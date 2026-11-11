"""One manual batch owns its immutable paths, destination and credentials."""
from __future__ import annotations

import os
import posixpath
import time
from copy import deepcopy
from pathlib import Path
from .p115_web import P115AuthError
from .fileactions import delete_source, move_failed, signature, path_lock


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class TransferMixin:
    def _job_update(self, job_id, **values):
        with self._guard:
            if self._job.get("id") == job_id:
                self._job.update(values)

    def _run_transfer(self, job_id, files, paths, target, cid, cfg, force, preserve, cancel):
        success = failed = skipped = processed = 0
        total = 0
        errors = []
        try:
            tasks = files.collect(paths, preserve_structure=preserve, cancelled=cancel.is_set)
            from .fileactions import contains
            if cfg.get('failure_move_enabled'):
                tasks = [task for task in tasks if not contains(cfg.get('failure_move_dir'), task['path'])]
            total = len(tasks)
            self._job_update(job_id, total=total, remaining=total)
            if cancel.is_set():
                raise InterruptedError("已停止文件收集")
            if not tasks:
                raise ValueError("选择的路径中没有符合扩展名条件的文件，请检查文件或设置")
            client = self._make_client(cfg)
            # A supplied cid still needs to match the submitted path. Never
            # reuse an id cached for a different Cookie/account or path.
            if cid is not None:
                from .remotefiles import browse_remote
                actual = browse_remote(client, str(cid), 0, 1)
                if actual["path"] != target:
                    raise ValueError("115目标目录与ID不一致，请重新选择目标")
                base_cid = int(cid)
            else:
                base_cid = None
            scope = self._account(cfg)
            with self._guard:
                history = deepcopy(self._history)
            confirmed = {self._done_key(row) for row in history if row.get("status") == "success"}
            dirs = {}
            failures = 0
            self._job_update(job_id, phase="running", message="正在手动补传")
            for task in tasks:
                if cancel.is_set():
                    raise InterruptedError("已停止，未完成文件可重新选择补传")
                path = task["path"]
                with path_lock(path):
                    rel = task.get("relative_dir") or ""
                    actual_target = posixpath.join(target, rel) if rel else target
                    record = {"name": os.path.basename(path), "path": path, "original_path": path, "remote_dir": actual_target,
                              "time": stamp(), "status": "failed", "message": "", "size": 0,
                              "account_scope": scope, "job_id": job_id,
                              "delete_status": "none", "move_status": "none"}
                    abort = False
                    self._job_update(job_id, current_file=path)
                    try:
                        path = files.validate(path, directory=False)
                        before = signature(path)
                        record.update(signature=list(before), size=before[0])
                        if not force and self._done_key(record) in confirmed:
                            record.update(status="skipped", message="相同账户、目标与文件签名已有成功记录")
                            skipped += 1
                            failures = 0
                        else:
                            # Directory errors are per-file outcomes too.
                            if base_cid is None:
                                base_cid = client.get_dir_id_by_path(target)
                            parent, cur = base_cid, ""
                            for name in (part for part in rel.split("/") if part):
                                cur = posixpath.join(cur, name)
                                if cur not in dirs:
                                    found = client.find_dir(parent, name)
                                    dirs[cur] = found if found is not None else client.make_dir(parent, name)
                                parent = dirs[cur]
                            result = client.push_file(Path(path), remote_dir_id=parent)
                            after = signature(path)
                            if before != after:
                                record["message"] = "文件在秒传期间发生变化，请稳定后重新补传"
                            elif result.get("ok") is True:
                                record.update(status="success", message=result.get("message") or "SHA1秒传成功",
                                              sha1=result.get("sha1", ""), pickcode=result.get("pickcode", ""))
                                success += 1
                                failures = 0
                                confirmed.add(self._done_key(record))
                            elif result.get("skipped"):
                                record.update(status="skipped", message=result.get("message") or "空文件或未满足条件")
                                skipped += 1
                                failures = 0
                            else:
                                record["message"] = result.get("message") or "115未确认秒传成功"
                    except P115AuthError as exc:
                        record["message"] = self._error(exc, cfg)
                        abort = True
                    except Exception as exc:
                        record["message"] = self._error(exc, cfg)
                    if record["status"] == "failed":
                        failed += 1
                        failures += 1
                        errors.append({"path": record["path"], "message": record["message"]})
                    processed += 1
                    with self._guard:
                        self._history.append(record)
                        self._history = self._history[-500:]
                    self._job_update(job_id, processed=processed, success=success, failed=failed, skipped=skipped,
                                     remaining=total - processed, errors=errors[-20:])
                    action = ('delete' if record['status'] == 'success' and cfg.get('delete_on_success') else
                              'move' if record['status'] == 'failed' and cfg.get('failure_move_enabled') else '')
                    if action:
                        record[action + '_status'] = 'pending'
                    saved = self._persist()  # Persist remote confirmation and action intent first.
                    if action:
                        try:
                            if not saved:
                                raise RuntimeError('结果未持久化，保留源文件')
                            if action == 'delete':
                                deleted, message = delete_source(path, record.get('signature'))
                                record['delete_status'] = 'success' if deleted else 'race_changed'
                            else:
                                roots = [p for p in paths if os.path.isdir(p) and contains(p, path)]
                                root = max(roots, key=len) if roots else None
                                moved, _ = move_failed(path, cfg['failure_move_dir'],
                                    preserve_root=root if cfg.get('failure_move_preserve_structure') else None,
                                    expected=record.get('signature'))
                                record.update(path=moved, move_status='success')
                                message = '已归档至：' + moved
                            record['message'] += '；' + message
                        except Exception as exc:
                            record[action + '_status'] = 'failed'
                            record['message'] += '；本地文件动作失败：' + self._error(exc, cfg)
                        self._persist()
                    if abort or failures >= 10:
                        raise RuntimeError("Cookie失效" if abort else "连续10个文件失败，已停止；未处理文件可再次补传")
            phase = "completed" if not failed else "completed_with_errors"
            self._job_update(job_id, phase=phase, message=f"完成：成功{success}、失败{failed}、跳过{skipped}")
        except InterruptedError as exc:
            self._job_update(job_id, phase="cancelled", message=str(exc), remaining=max(0, total - processed))
        except Exception as exc:
            self._job_update(job_id, phase="failed", message=self._error(exc, cfg), remaining=max(0, total - processed))
        finally:
            self._job_update(job_id, current_file="", finished_at=stamp())
            self._persist()
            with self._guard:
                if self._job.get("id") == job_id:
                    self._running = False

    @staticmethod
    def _done_key(row):
        return (row.get("account_scope"), row.get("remote_dir"), row.get("path"),
                tuple(row.get("signature") or []))
