"""Durable action bookkeeping, separate from the remote transfer outcome."""
from copy import deepcopy
from pathlib import Path
from .config import account_scope, clean_message, signature, split_paths, task_key
from .fileactions import contains, delete_source, move_failed, signature as file_signature


class ActionsMixin:
    def _resolve_qb_file(self, file, target):
        cfg = getattr(self._job_context, 'config', self._config)
        key = task_key(file['path'], target, account_scope(cfg))
        with self._state_lock:
            row = deepcopy(self._ledger.get(key, {}))
        relocated = row.get('relocated_path')
        if relocated and not Path(file['path']).exists():
            file = {**file, 'original_path': file['path'], 'path': relocated}
            key = task_key(relocated, target, account_scope(cfg))
            with self._state_lock:
                row = deepcopy(self._ledger.get(key, row))
        # Only our durable deletion intent/confirmation can explain a missing file.
        if (not Path(file['path']).exists() and row.get('status') == 'success'
                and row.get('delete_status') in {'pending', 'success'}
                and row.get('signature', [None])[0] == file.get('size')):
            return {**file, 'ready': True, 'confirmed': True,
                    'signature': tuple(row['signature']), 'reason': '已秒传并按设置删除'}
        return file

    def _file_action(self, item, result, cfg, source, target, before, ok, skipped):
        path, scope = item['path'], account_scope(cfg)
        key = task_key(path, target, scope)
        original = item.get('original_path', path)
        result['original_path'] = original
        with self._state_lock:
            row = self._ledger.setdefault(key, {'path': path, 'target': target, 'scope': scope,
                'signature': signature(item), 'status': 'failed'})
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
        # The upload history is already durable; this checkpoint adds action intent.
        try:
            if not self._persist():
                raise RuntimeError('结果未持久化，保留源文件')
            if action == 'delete':
                done, message = delete_source(path, before)
                result[field] = row[field] = 'success' if done else 'race_changed'
            else:
                roots = [root for root in split_paths(cfg['watch_paths']) if contains(root, path)]
                root = max(roots, key=len) if roots else str(Path(path).parent)
                moved, _ = move_failed(path, cfg['failure_move_dir'], expected=before,
                    preserve_root=root if cfg.get('failure_move_preserve_structure') else None)
                result[field] = row[field] = 'success'
                result['path'] = moved
                message = '已归档至：' + moved
                if moved != path:
                    live = self._file_item(moved)
                    row['relocated_path'] = moved
                    with self._state_lock:
                        self._ledger[task_key(moved, target, scope)] = {**row, 'path': moved,
                            'original_path': original, 'relocated_path': '', 'signature': signature(live)}
                        retry = self._queue.pending.pop(path, None)
                        if retry:
                            self._queue.pending[moved] = {**retry, **live, 'original_path': original,
                                'signature': signature(live)}
                        old = self._inventory.pop(path, None)
                        if old:
                            self._inventory[moved] = {**old, **live, 'original_path': original}
            result['message'] += '；' + message
        except Exception as exc:
            result[field] = row[field] = 'failed'
            result['message'] += '；本地文件动作失败：' + clean_message(exc, cfg)
        with self._state_lock:
            for history in reversed(self._history):
                if history.get('path') == path and history.get('remote_dir') == target:
                    history.update({k: result[k] for k in ('original_path', 'path', field, 'message') if k in result})
                    break
        self._persist()
