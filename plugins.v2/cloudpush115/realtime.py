"""Bounded event callbacks and durable, generation-scoped background ingestion."""
from copy import deepcopy
from pathlib import Path
import os
import stat
import time
import threading

from .config import account_scope, remote_path, signature, split_paths, task_key
from .fileactions import contains, signature as file_signature
from .scanner import MediaScanner


def value(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class RealtimeMixin:
    def _realtime_init(self):
        self._live_queue = {}
        self._observer = None
        self._monitor_status = '未启用'

    def _live_enabled(self, cfg=None):
        cfg = cfg or self._config
        return self._loaded and not self._service_stopped and cfg['enabled'] and cfg.get('realtime_enabled', True)

    def _on_transfer_complete(self, event):
        data = value(event, 'event_data', {}) or {}
        transfer = value(data, 'transferinfo')
        if transfer is None or value(transfer, 'success', True) is not True:
            return
        # MoviePilot TransferInfo.target_item and file_list_new are target paths.
        # Never fall back to event.fileitem: that is the download source.
        target = value(transfer, 'target_item')
        storage = value(target, 'storage') if target else None
        if storage and str(storage).lower() not in {'local', 'storagetype.local'}:
            return
        paths = list(value(transfer, 'file_list_new', []) or [])
        if target:
            paths.append(value(target, 'path'))
        for path in paths:
            if isinstance(path, str):
                self._ingest_path(path)
            elif path is not None:
                self._ingest_path(value(path, 'path', ''))

    def _ingest_path(self, path, generation=None, directory=False):
        """Only metadata/config checks + durable queue write; no hashing or network."""
        with self._state_lock:
            if not self._live_enabled() or (generation is not None and not self._is_current(generation)):
                return False
            cfg = deepcopy(self._config)
            if not isinstance(path, str) or not os.path.isabs(path):
                return False
            path = os.path.abspath(path)
            if not any(contains(root, path) for root in split_paths(cfg['watch_paths'])):
                return False
            if any(contains(root, path) for root in split_paths(cfg.get('protected_paths'))):
                return False
            extensions = MediaScanner([x.strip() for x in cfg['extensions'].replace('，', ',').split(',') if x.strip()] or None).extensions
            if not directory and Path(path).suffix.lower().lstrip('.') not in extensions:
                return False
            existing = self._live_queue.get(path, {})
            self._live_queue[path] = {**existing, 'path': path, 'directory': directory,
                'seen_at': time.time(), 'due_at': time.time() + cfg.get('realtime_settle', 2),
                'target': cfg['remote_dir'], 'scope': account_scope(cfg)}
        self._persist()
        return True

    def _stop_monitor(self):
        observer, self._observer = self._observer, None
        if observer is not None:
            # Some backends block inside stop(), before their join timeout applies.
            def finish():
                try:
                    observer.stop()
                    observer.join(timeout=2)
                except Exception:
                    pass
            closer = threading.Thread(target=finish, name='CloudPush115MonitorStop', daemon=True)
            closer.start()
            closer.join(timeout=3)
        self._monitor_status = '未启用'

    def _start_monitor(self, cfg, generation):
        if not self._live_enabled(cfg):
            return
        try:
            # iSH exposes inotify symbols but its emulation can hang at shutdown.
            if '-ish' in os.uname().release:
                self._monitor_status = '当前内核使用整理事件 + 定期补扫'
                return
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
            plugin = self
            class Handler(FileSystemEventHandler):
                def on_created(self, event):
                    plugin._ingest_path(event.src_path, generation, event.is_directory)
                def on_modified(self, event):
                    if not event.is_directory:
                        plugin._ingest_path(event.src_path, generation)
                def on_moved(self, event):
                    plugin._ingest_path(event.dest_path, generation, event.is_directory)
            observer = Observer()
            count = 0
            for root in split_paths(cfg['watch_paths']):
                if os.path.isdir(root):
                    observer.schedule(Handler(), root, recursive=True)
                    count += 1
            if not count:
                self._monitor_status = '目录尚未就绪；整理事件 + 定期补扫'
                return
            observer.start()
            self._observer = observer
            self._monitor_status = '整理事件 + 原生监控 + 定期补扫'
        except Exception as exc:
            if 'observer' in locals():
                try:
                    observer.stop()
                    if observer.is_alive(): observer.join(timeout=3)
                except Exception:
                    pass
            self._monitor_status = '原生监控不可用；整理事件 + 定期补扫'

    def _live_tick(self, generation):
        if not self._is_current(generation) or not self._live_enabled():
            return
        with self._state_lock:
            due = any(x.get('due_at', 0) <= time.time() for x in self._live_queue.values())
        if due:
            self._enqueue('live')

    def _drain_live(self, cfg, gen):
        with self._state_lock:
            due = [deepcopy(x) for x in self._live_queue.values() if x.get('due_at', 0) <= time.time()]
        for queued in due:
            if not self._is_current(gen) or not self._live_enabled(cfg):
                return
            path = queued['path']
            if queued.get('scope') != account_scope(cfg) or queued.get('target') != cfg['remote_dir']:
                continue  # Keep original task scoped, never silently redirect it.
            if not any(contains(root, path) for root in split_paths(cfg['watch_paths'])):
                continue
            if queued.get('directory'):
                scanner = MediaScanner([x.strip() for x in cfg['extensions'].split(',') if x.strip()] or None)
                for item in scanner.walk_files([path], stop=lambda: not self._is_current(gen)):
                    self._ingest_path(item['path'], gen)
                self._finish_live(queued)
                continue
            try:
                full = file_signature(path)
                item = self._file_item(path)
                old = queued.get('observed')
                if old is None or tuple(old) != full:
                    with self._state_lock:
                        current = self._live_queue.get(path)
                        if current and current.get('seen_at') == queued.get('seen_at'):
                            current.update(observed=list(full), due_at=time.time() + cfg['realtime_settle'])
                    self._persist()
                    continue
                if not cfg['cookie']:
                    self._queue_row(item, 'blocked', '尚未填写115网页Cookie')
                    with self._state_lock:
                        self._live_queue[path]['due_at'] = time.time() + 30
                    self._persist()
                    continue
                with self._state_lock:
                    retry = deepcopy(self._queue.pending.get(path))
                    ledger = deepcopy(self._ledger.get(task_key(path, cfg['remote_dir'], account_scope(cfg)), {}))
                if retry and retry.get('signature') == signature(item):
                    self._finish_live(queued)
                    continue  # Existing retry interval/budget takes precedence.
                if ledger.get('status') in {'legacy', 'skipped'} and ledger.get('signature') == signature(item):
                    self._finish_live(queued)
                    continue
                self._transfer(item, cfg, source='local')
                self._finish_live(queued)
            except (OSError, ValueError):
                self._finish_live(queued)

    def _finish_live(self, queued):
        with self._state_lock:
            current = self._live_queue.get(queued['path'])
            if current and current.get('seen_at') == queued.get('seen_at'):
                self._live_queue.pop(queued['path'], None)
        self._persist()
