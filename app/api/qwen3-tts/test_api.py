"""
Qwen3-TTS API 服务自动测试
用法：先启动 server.py，再运行此脚本
"""
import os
import sys
import time
import json
import unittest
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8420"


def _request(method, path, data=None):
    url = BASE_URL + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return json.loads(raw), e.code
        except (json.JSONDecodeError, ValueError):
            return {"raw": raw.decode(errors="replace")}, e.code


class TestTTSAPI(unittest.TestCase):

    def test_01_health(self):
        """健康检查"""
        resp, code = _request("GET", "/tts/health")
        self.assertEqual(code, 200)
        self.assertEqual(resp["status"], "ok")
        print("[OK] health ok")

    def test_02_submit(self):
        """提交任务（带 speaker 和 instruct），返回 task_id"""
        resp, code = _request("POST", "/tts/submit", {
            "text": "你好，欢迎使用语音合成服务。今天天气真不错，我们一起去公园散步吧。",
            "language": "Chinese",
            "speaker": "Dylan",
            "instruct": "愉快，轻松，语速中等",
        })
        self.assertEqual(code, 202)
        self.assertIn("task_id", resp)
        self.assertIn("position", resp)
        # 验证 task_id 带日期前缀
        self.assertRegex(resp["task_id"], r"^\d{8}_[0-9a-f]+$")
        self.__class__.task_id = resp["task_id"]
        print(f"[OK] 提交成功，task_id={resp['task_id']}，排队位置={resp['position']}")

    def test_03_submit_no_text(self):
        """空文本应返回 400"""
        resp, code = _request("POST", "/tts/submit", {"text": ""})
        self.assertEqual(code, 400)
        print("[OK] 空文本校验通过")

    def test_04_status_pending_or_processing(self):
        """查询刚提交的任务状态（应为 pending 或 processing）"""
        resp, code = _request("GET", f"/tts/status/{self.task_id}")
        self.assertEqual(code, 200)
        self.assertIn(resp["status"], ("pending", "processing", "success"))
        print(f"[OK] 状态查询: {resp['status']}")

    def test_05_status_not_found(self):
        """不存在的 task_id 返回 404"""
        resp, code = _request("GET", "/tts/status/no_such_id")
        self.assertEqual(code, 404)
        print("[OK] 不存在任务校验通过")

    def test_06_queue_info(self):
        """查看队列概况"""
        resp, code = _request("GET", "/tts/queue")
        self.assertEqual(code, 200)
        for key in ("queue_size", "total", "pending", "processing", "success", "failed"):
            self.assertIn(key, resp)
        print(f"[OK] 队列概况: {resp}")

    def test_07_wait_for_success(self):
        """等待任务完成，验证最终状态为 success"""
        max_wait = 600  # 最多等 10 分钟
        interval = 5
        elapsed = 0
        while elapsed < max_wait:
            resp, code = _request("GET", f"/tts/status/{self.task_id}")
            status = resp["status"]
            if status in ("success", "failed"):
                print(f"[OK] 任务最终状态: {status}（耗时 {elapsed}s）")
                break
            time.sleep(interval)
            elapsed += interval
        else:
            self.fail(f"等待超时（>{max_wait}s），任务未完成")

        self.assertEqual(status, "success")
        self.assertIn("download_url", resp)

    def test_08_download(self):
        """下载生成的音频文件"""
        resp, code = _request("GET", f"/tts/status/{self.task_id}")
        self.assertEqual(resp["status"], "success")

        download_url = BASE_URL + resp["download_url"]
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=30) as resp_io:
            data = resp_io.read()
            self.assertGreater(len(data), 1000)  # 至少 1KB
            self.assertEqual(resp_io.status, 200)

        # 保存到本地验证
        out_path = os.path.join(os.path.dirname(__file__), "test_download.wav")
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[OK] 下载成功，{len(data)} 字节，已保存到 {out_path}")

    def test_09_download_404(self):
        """下载不存在的任务应返回 404"""
        resp, code = _request("GET", "/tts/download/no_such_id")
        self.assertEqual(code, 404)
        print("[OK] 下载不存在任务校验通过")

    def test_10_multi_role_emotion(self):
        """多角色情感测试：旁白 + 愤怒 + 温柔"""
        cases = [
            {
                "text": "夜幕降临，城市的灯火渐渐亮起。林轩独自站在天台上，望着远处出神。",
                "speaker": "Uncle_Fu",
                "instruct": "沉稳，客观，语速中等偏慢",
            },
            {
                "text": "他们凭什么这样对我？我辛辛苦苦这么久，一句话就把我打发了？",
                "speaker": "Dylan",
                "instruct": "愤怒，语气强烈，语速稍快",
            },
            {
                "text": "林轩，你先冷静下来。我知道你很难过，但生气解决不了问题。",
                "speaker": "Vivian",
                "instruct": "温柔，关切，语速平缓",
            },
        ]
        task_ids = []
        for c in cases:
            resp, code = _request("POST", "/tts/submit", {
                "text": c["text"],
                "language": "Chinese",
                "speaker": c["speaker"],
                "instruct": c["instruct"],
            })
            self.assertEqual(code, 202)
            task_ids.append(resp["task_id"])
            print(f"  提交 {c['speaker']}({c['instruct']}) → {resp['task_id']}")

        # 等待全部完成
        max_wait = 600
        interval = 5
        elapsed = 0
        while elapsed < max_wait:
            done = True
            for tid in task_ids:
                r, _ = _request("GET", f"/tts/status/{tid}")
                if r["status"] not in ("success", "failed"):
                    done = False
                    break
            if done:
                break
            time.sleep(interval)
            elapsed += interval
        else:
            self.fail("多角色任务等待超时")

        # 验证全部成功并下载
        for i, tid in enumerate(task_ids):
            r, _ = _request("GET", f"/tts/status/{tid}")
            self.assertEqual(r["status"], "success")
            req = urllib.request.Request(BASE_URL + r["download_url"])
            with urllib.request.urlopen(req, timeout=30) as resp_io:
                data = resp_io.read()
                self.assertGreater(len(data), 1000)
            out_path = os.path.join(os.path.dirname(__file__), f"test_role_{i}.wav")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  [OK] {cases[i]['speaker']} 下载成功，{len(data)} 字节")

        print("[OK] 多角色情感测试全部通过")


if __name__ == "__main__":
    print("=" * 60)
    print("Qwen3-TTS API 自动测试")
    print(f"服务地址: {BASE_URL}")
    print("=" * 60)
    unittest.main(verbosity=2)
