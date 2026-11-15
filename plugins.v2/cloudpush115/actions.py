"""Durable remote-success and exact-path local action bookkeeping."""
from copy import deepcopy
from pathlib import Path
import os
import uuid
from .config import account_scope, clean_message, signature, split_paths, task_key
from .fileactions import (contains, delete_source, move_failed, signature as file_signature,
                          check_policy, hardlink_destination, link_failed)


class ActionsMixin:
    def _resolve_qb_file(self, file, target):
        cfg = getattr(self._job_context, 'config', self._config)
        key = task_key(file['path'], target, account_scope(cfg))
        with self._state_lock:
            row = deepcopy(self._ledger.get(key, {}))
        relocated = row.get('relocated_path')
        follow_retry = cfg.get('failure_action') == 'hardlink' and row.get('retry_path') and Path(row['retry_path']).exists()
        if relocated and (not Path(file['path']).exists() or follow_retry):
            file = {**file, 'original_path': file['path'], 'path': relocated}
            key = task_key(relocated, target, account_scope(cfg))
            with self._state_lock:
                row = deepcopy(self._ledger.get(key, row))
        if (not Path(file['path']).exists() and row.get('status') == 'success'
                and row.get('delete_status') in {'pending', 'success'}
                and row.get('signature', [None])[0] == file.get('size')):
            return {**file, 'ready': True, 'confirmed': True,
                    'signature': tuple(row['signature']), 'reason': '已秒传并按设置删除'}
        return file

    def _sync_group(self, row, target, scope):
        """Keep only explicitly registered aliases; never search for inode siblings."""
        with self._state_lock:
            for path, entry in row.get('managed_paths', {}).items():
                key = task_key(path, target, scope)
                saved = {**row, 'path': path, 'signature': [entry['signature'][0], entry['signature'][1], entry['signature'][3]]}
                existing = self._ledger.get(key, {})
                if (existing.get('action_group') and existing.get('action_group') != row.get('action_group')
                        and existing.get('signature') != saved['signature']):
                    continue
                self._ledger[key] = deepcopy(saved)
            if row.get('status') == 'success' and row.get('delete_status'):
                aliases = row.get('managed_paths', {})
                for history in reversed(self._history):
                    if history.get('path') in aliases and history.get('remote_dir') == target and history.get('status') == 'success':
                        history['delete_status'] = row['delete_status']
                        break

    def _cleanup_links(self, row, cfg, target, scope):
        if not cfg.get('delete_on_success'):
            return '本地链接按设置保留'
        managed = row.get('managed_paths', {})
        row['delete_status'] = 'pending'
        self._sync_group(row, target, scope)
        if not self._persist():
            return '结果未持久化，保留本地链接'
        messages = []
        for path, entry in managed.items():
            if entry.get('delete_status') == 'success':
                continue
            try:
                if not os.path.lexists(path):
                    entry['delete_status'] = 'success'
                    continue
                protected = split_paths(cfg.get('protected_paths'))
                strict = cfg.get('hardlink_only', False)
                # Keep the two-argument call for existing integrations/mocks.
                check_policy(path, protected, strict)
                if protected or strict:
                    done, message = delete_source(path, entry['signature'], protected, strict)
                else:
                    done, message = delete_source(path, entry['signature'])
                entry['delete_status'] = 'success' if done else 'race_changed'
                messages.append(message)
            except Exception as exc:
                entry['delete_status'] = 'failed'
                messages.append(clean_message(exc, cfg))
            row['delete_status'] = 'success' if all(x.get('delete_status') == 'success' for x in managed.values()) else 'failed'
            self._sync_group(row, target, scope)
            if not self._persist():
                break
        row['delete_status'] = 'success' if all(x.get('delete_status') == 'success' for x in managed.values()) else 'failed'
        self._sync_group(row, target, scope)
        self._persist()
        return '；'.join(messages) or '登记的本地链接已清理'

    def _resume_file_actions(self, item, cfg, source, target):
        path, scope = item['path'], account_scope(cfg)
        key = task_key(path, target, scope)
        with self._state_lock:
            row = deepcopy(self._ledger.get(key, {}))
        if not row:
            return None
        if row.get('status') == 'success' and not row.get('managed_paths') and row.get('verified_file_signature'):
            row['action_group'] = uuid.uuid4().hex
            row['managed_paths'] = {path: {'signature': row['verified_file_signature']}}
        entry = row.get('managed_paths', {}).get(path)
        if entry:
            try:
                if file_signature(path) != tuple(entry['signature']):
                    return None
            except FileNotFoundError:
                if row.get('status') != 'success':
                    return None
            except (OSError, ValueError):
                return None
        elif row.get('signature') != signature(item):
            return None
        if row.get('status') == 'success' and row.get('managed_paths'):
            message = self._cleanup_links(row, cfg, target, scope)
            with self._state_lock:
                for alias in row['managed_paths']:
                    pending = self._queue.pending.get(alias)
                    if pending and pending.get('scope', scope) == scope and pending.get('remote_dir', target) == target:
                        self._queue.remove(alias)
            self._persist()
            return {'ok': True, 'reuse': True, 'delete_status': row.get('delete_status'), 'message': message}
        primary = row.get('retry_path')
        if primary and primary != path and Path(primary).exists():
            expected = row.get('managed_paths', {}).get(primary, {}).get('signature')
            try:
                if not expected or file_signature(primary) != tuple(expected):
                    return None
            except (OSError, ValueError):
                return None
            # Recover a crash after publishing the link but before queue handoff.
            live = self._file_item(primary)
            with self._state_lock:
                retry = self._queue.pending.pop(path, None)
                if retry:
                    self._queue.pending[primary] = {**retry, **live, 'original_path': path,
                                                    'signature': signature(live)}
                old = self._inventory.get(path)
                if old:
                    old.update(status='retry', message='失败硬链接已登记，等待重试')
                    self._inventory[primary] = {**old, **live, 'original_path': path}
            self._persist()
            return {'ok': False, 'relocated': True, 'message': '已登记失败硬链接，由重试路径按间隔继续处理'}
        return None

    def _recover_file_actions(self, cfg, gen):
        """Resume interrupted cleanup even after original paths disappeared."""
        scope = account_scope(cfg)
        with self._state_lock:
            rows = list(deepcopy(self._ledger).values())
        seen = set()
        for row in rows:
            if not self._is_current(gen):
                break
            if (row.get('status') == 'success' and not row.get('managed_paths')
                    and row.get('verified_file_signature') and cfg.get('delete_on_success')):
                row['action_group'] = uuid.uuid4().hex
                row['managed_paths'] = {row['path']: {'signature': row['verified_file_signature']}}
            group = row.get('action_group')
            if (not group or group in seen or row.get('scope') != scope
                    or row.get('status') != 'success' or row.get('delete_status') == 'success'):
                continue
            seen.add(group)
            with self._transfer_lock:
                self._cleanup_links(row, cfg, row['target'], scope)

    def _file_action(self, item, result, cfg, source, target, before, ok, skipped):
        path, scope = item['path'], account_scope(cfg)
        key = task_key(path, target, scope)
        original = item.get('original_path', path)
        result['original_path'] = original
        with self._state_lock:
            row = deepcopy(self._ledger.setdefault(key, {'path': path, 'target': target, 'scope': scope,
                'signature': signature(item), 'status': 'failed'}))
            if not ok:
                row['attempts'] = int(row.get('attempts', 0)) + 1
            attempts = row.get('attempts', 0)
            if source != 'qb':
                attempts = self._queue.pending.get(path, {}).get('attempts', attempts)
        move_due = cfg.get('failure_move_on') == 'each_failure' or (cfg.get('max_attempts', 0) and attempts > cfg['max_attempts'])
        action = ('delete' if ok and cfg.get('delete_on_success') else
                  'move' if not ok and not skipped and cfg.get('failure_move_enabled') and move_due else '')
        if not action:
            return
        field = action + '_status'
        result[field] = row[field] = 'pending'
        row['action_signature'] = before
        try:
            if before is None:
                raise RuntimeError('文件签名未确认，保留本地文件')
            if row.get('managed_paths', {}).get(path, {}).get('signature') != list(before):
                row['managed_paths'] = {path: {'signature': list(before)}}
                row['action_group'] = uuid.uuid4().hex
            row.setdefault('action_group', uuid.uuid4().hex)
            row.setdefault('managed_paths', {path: {'signature': list(before)}})
            self._sync_group(row, target, scope)
            if not self._persist():
                raise RuntimeError('结果未持久化，保留源文件')
            if action == 'delete':
                message = self._cleanup_links(row, cfg, target, scope)
                result[field] = row[field]
            else:
                protected = split_paths(cfg.get('protected_paths'))
                check_policy(path, protected)
                roots = [root for root in split_paths(cfg['watch_paths']) if contains(root, path)]
                root = max(roots, key=len) if roots else str(Path(path).parent)
                preserve_root = root if cfg.get('failure_move_preserve_structure') else None
                if cfg.get('failure_action') == 'hardlink':
                    if contains(cfg['failure_move_dir'], path):
                        moved = path
                    else:
                        moved = row.get('retry_path') or hardlink_destination(path, cfg['failure_move_dir'], preserve_root)
                        if os.path.lexists(moved) and (not row.get('retry_path') or file_signature(moved) != tuple(before)):
                            base = Path(moved)
                            moved = str(base.with_name(base.stem + '-' + uuid.uuid4().hex + base.suffix))
                        if any(contains(p, moved) for p in protected):
                            raise ValueError('失败目录位于受保护源目录')
                        row['retry_path'] = moved
                        row['managed_paths'][moved] = {'signature': list(before)}
                        self._sync_group(row, target, scope)
                        if not self._persist():
                            raise RuntimeError('硬链接意图未持久化，保留源文件')
                        link_failed(path, moved, before)
                    message = '已保留原路径并登记失败硬链接：' + moved
                else:
                    moved, _ = move_failed(path, cfg['failure_move_dir'], expected=before, preserve_root=preserve_root)
                    row['managed_paths'] = {moved: {'signature': list(file_signature(moved))}}
                    message = '已归档至：' + moved
                result[field] = row[field] = 'success'
                result['path'] = moved
                if moved != path:
                    live = self._file_item(moved)
                    row['relocated_path'] = moved
                    row['retry_path'] = moved
                    self._sync_group(row, target, scope)
                    with self._state_lock:
                        self._ledger[key] = {**row, 'path': path, 'signature': signature(item)}
                        retry = self._queue.pending.pop(path, None)
                        if retry:
                            self._queue.pending[moved] = {**retry, **live, 'original_path': original,
                                'signature': signature(live)}
                        old = self._inventory.get(path)
                        if old:
                            if cfg.get('failure_action') != 'hardlink':
                                self._inventory.pop(path, None)
                            else:
                                old.update(status='retry', message='失败硬链接已入队，等待重试')
                            self._inventory[moved] = {**old, **live, 'original_path': original}
            result['message'] += '；' + message
        except Exception as exc:
            result[field] = row[field] = 'failed'
            result['message'] += '；本地文件动作失败：' + clean_message(exc, cfg)
        with self._state_lock:
            if row.get('managed_paths'):
                self._sync_group(row, target, scope)
            else:
                self._ledger[key] = row
            for history in reversed(self._history):
                if history.get('path') == path and history.get('remote_dir') == target:
                    history.update({k: result[k] for k in ('original_path', 'path', field, 'message') if k in result})
                    break
        self._persist()
