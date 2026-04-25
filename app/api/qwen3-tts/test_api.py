"""
Qwen3-TTS API 服务自动测试
用法：先启动 server.py，再运行此脚本
"""
import os
import unittest
import yaml

from tts_client import TtsClient

# 从 config.yaml 读取服务地址
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)
BASE_URL = _cfg.get("api", {}).get("base_url", "http://127.0.0.1:8420")

client = TtsClient(BASE_URL)


class TestTTSAPI(unittest.TestCase):

    def test_01_health(self):
        """健康检查"""
        self.assertTrue(client.health())
        print("[OK] health ok")

    def test_02_submit(self):
        """提交任务（带 speaker 和 instruct），返回 task_id"""
        result = client.submit(
            text="你好，欢迎使用语音合成服务。今天天气真不错，我们一起去公园散步吧。",
            language="Chinese",
            speaker="Dylan",
            instruct="愉快，轻松，语速中等",
        )
        self.assertFalse(result.error, f"提交失败: {result.error}")
        self.assertRegex(result.task_id, r"^\d{8}_[0-9a-f]+$")
        self.__class__.task_id = result.task_id
        print(f"[OK] 提交成功，task_id={result.task_id}，排队位置={result.position}")

    def test_03_submit_no_text(self):
        """空文本应返回错误"""
        result = client.submit(text="")
        self.assertTrue(result.error)
        print("[OK] 空文本校验通过")

    def test_04_status_pending_or_processing(self):
        """查询刚提交的任务状态"""
        sr = client.status(self.task_id)
        self.assertIn(sr.status, ("pending", "processing", "success"))
        print(f"[OK] 状态查询: {sr.status}")

    def test_05_status_not_found(self):
        """不存在的 task_id 返回错误"""
        sr = client.status("no_such_id")
        self.assertTrue(sr.error)
        print("[OK] 不存在任务校验通过")

    def test_06_queue_info(self):
        """查看队列概况"""
        info = client.queue_info()
        for key in ("queue_size", "total", "pending", "processing", "success", "failed"):
            self.assertIn(key, info)
        print(f"[OK] 队列概况: {info}")

    def test_07_wait_for_success(self):
        """等待任务完成，验证最终状态为 success"""
        sr = client.wait(self.task_id)
        self.assertTrue(sr.ok, f"任务未完成: {sr.status} {sr.error}")
        print(f"[OK] 任务最终状态: {sr.status}")

    def test_08_download(self):
        """下载生成的音频文件"""
        dl = client.download(self.task_id)
        self.assertTrue(dl.ok, f"下载失败: {dl.error}")
        self.assertGreater(len(dl.data), 1000)

        out_path = os.path.join(os.path.dirname(__file__), "test_output", "test_download.wav")
        with open(out_path, "wb") as f:
            f.write(dl.data)
        print(f"[OK] 下载成功，{len(dl.data)} 字节，已保存到 {out_path}")

    def test_09_download_404(self):
        """下载不存在的任务应返回错误"""
        dl = client.download("no_such_id")
        self.assertFalse(dl.ok)
        print("[OK] 下载不存在任务校验通过")

    def test_10_multi_role_emotion(self):
        """多角色情感测试：旁白 + 愤怒 + 温柔"""
        cases = [
            ("夜幕降临，城市的灯火渐渐亮起。林轩独自站在天台上，望着远处出神。",
             "Uncle_Fu", "沉稳，客观，语速中等偏慢"),
            ("他们凭什么这样对我？我辛辛苦苦这么久，一句话就把我打发了？",
             "Dylan", "愤怒，语气强烈，语速稍快"),
            ("林轩，你先冷静下来。我知道你很难过，但生气解决不了问题。",
             "Vivian", "温柔，关切，语速平缓"),
        ]
        task_ids = []
        for text, speaker, instruct in cases:
            r = client.submit(text=text, speaker=speaker, instruct=instruct)
            self.assertFalse(r.error)
            task_ids.append(r.task_id)
            print(f"  提交 {speaker}({instruct}) → {r.task_id}")

        # 等待全部完成
        for i, tid in enumerate(task_ids):
            sr = client.wait(tid)
            self.assertTrue(sr.ok, f"任务 {tid} 未完成: {sr.status}")
            dl = client.download(tid)
            self.assertTrue(dl.ok, f"下载 {tid} 失败: {dl.error}")
            self.assertGreater(len(dl.data), 1000)
            out_path = os.path.join(os.path.dirname(__file__), "test_output", f"test_role_{i}.wav")
            with open(out_path, "wb") as f:
                f.write(dl.data)
            print(f"  [OK] {cases[i][1]} 下载成功，{len(dl.data)} 字节")

        print("[OK] 多角色情感测试全部通过")


if __name__ == "__main__":
    print("=" * 60)
    print("Qwen3-TTS API 自动测试")
    print(f"服务地址: {BASE_URL}")
    print("=" * 60)
    unittest.main(verbosity=2)
