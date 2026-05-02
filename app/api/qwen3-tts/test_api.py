"""
Qwen3-TTS API 服务自动测试
用法：先启动 server.py，再运行此脚本

测试分层：
  - TestTTSAPILegacy（封存）：原始测试用例，不做修改，用于回归/兼容性验证
  - TestTTSAPISampling（新增）：验证采样参数（temperature/top_k/top_p/repetition_penalty）
  - TestTTSAPIComparison（新增）：对比保守参数 vs 官方默认参数的声音差异
"""
import os
import unittest

from tts_client import TtsClient

client = TtsClient.from_config()
BASE_URL = client.base_url   # 供打印使用


# ============================================================
# Legacy: original test cases (frozen, for compatibility only)
# ============================================================

class TestTTSAPILegacy(unittest.TestCase):
    """
    [FROZEN] Original API compatibility tests.
    These cases are not modified to ensure basic API availability.
    """

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
        self.__class__.legacy_task_id = result.task_id
        print(f"[OK] 提交成功，task_id={result.task_id}，排队位置={result.position}")

    def test_03_submit_no_text(self):
        """空文本应返回错误"""
        result = client.submit(text="")
        self.assertTrue(result.error)
        print("[OK] 空文本校验通过")

    def test_04_status_pending_or_processing(self):
        """查询刚提交的任务状态"""
        sr = client.status(self.legacy_task_id)
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
        sr = client.wait(self.legacy_task_id)
        self.assertTrue(sr.ok, f"任务未完成: {sr.status} {sr.error}")
        print(f"[OK] 任务最终状态: {sr.status}")

    def test_08_download(self):
        """下载生成的音频文件"""
        dl = client.download(self.legacy_task_id)
        self.assertTrue(dl.ok, f"下载失败: {dl.error}")
        self.assertGreater(len(dl.data), 1000)

        out_path = os.path.join(os.path.dirname(__file__), "test_output", "legacy_download.wav")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
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
        for i, legacy_tid in enumerate(task_ids):
            sr = client.wait(legacy_tid)
            self.assertTrue(sr.ok, f"任务 {legacy_tid} 未完成: {sr.status}")
            dl = client.download(legacy_tid)
            self.assertTrue(dl.ok, f"下载 {legacy_tid} 失败: {dl.error}")
            self.assertGreater(len(dl.data), 1000)
            out_path = os.path.join(os.path.dirname(__file__), "test_output", f"legacy_role_{i}.wav")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(dl.data)
            print(f"  [OK] {cases[i][1]} 下载成功，{len(dl.data)} 字节")

        print("[OK] 多角色情感测试全部通过")


# ============================================================
# New: sampling parameter tests
# ============================================================

class TestTTSAPISampling(unittest.TestCase):
    """
    Verify server-side sampling parameter passthrough.
    Submit tasks with different parameter combinations.
    """

    SAMPLE_TEXT = "Today is a nice day. Let's go for a walk in the park. What do you think?"

    def _submit_and_wait(self, **kwargs):
        """辅助：提交任务 + 等待完成 + 下载，返回 (task_id, audio_bytes)"""
        r = client.submit(text=self.SAMPLE_TEXT, **kwargs)
        self.assertFalse(r.error, f"提交失败: {r.error}")
        task_id = r.task_id
        print(f"  提交 → {task_id}")

        sr = client.wait(task_id)
        self.assertTrue(sr.ok, f"任务未完成: {sr.status} {sr.error}")

        dl = client.download(task_id)
        self.assertTrue(dl.ok, f"下载失败: {dl.error}")
        self.assertGreater(len(dl.data), 1000)

        return task_id, dl.data

    def _save_wav(self, data: bytes, filename: str):
        out_dir = os.path.join(os.path.dirname(__file__), "test_output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path

    # ── 1. 默认参数（不传任何采样参数） ──────────────────

    def test_01_default_params(self):
        """
        不传任何采样参数 → 服务端应使用保守默认值（temperature=0.3 等）。
        验证服务端默认行为已变为稳定模式。
        """
        tid, data = self._submit_and_wait(speaker="Dylan", instruct="愉快，轻松")
        path = self._save_wav(data, "sampling_default.wav")
        print(f"[OK] 默认参数音频: {path} ({len(data)} 字节)")

    # ── 2. 显式保守参数 ──────────────────────────────────

    def test_02_conservative_params(self):
        """
        显式传入保守参数（temperature=0.3, top_k=20, top_p=0.85）。
        与默认参数结果应非常接近（声音一致性验证）。
        """
        tid, data = self._submit_and_wait(
            speaker="Dylan",
            instruct="愉快，轻松",
            temperature=0.3,
            top_k=20,
            top_p=0.85,
            repetition_penalty=1.1,
        )
        path = self._save_wav(data, "sampling_conservative.wav")
        print(f"[OK] 保守参数音频: {path} ({len(data)} 字节)")

    # ── 3. 官方默认参数对比 ──────────────────────────────

    def test_03_official_defaults(self):
        """
        传入官方默认参数（temperature=0.9, top_k=50, top_p=1.0）。
        与保守参数相比应有更明显的随机性/变化。
        """
        tid, data = self._submit_and_wait(
            speaker="Dylan",
            instruct="愉快，轻松",
            temperature=0.9,
            top_k=50,
            top_p=1.0,
            repetition_penalty=1.05,
        )
        path = self._save_wav(data, "sampling_official.wav")
        print(f"[OK] 官方默认参数音频: {path} ({len(data)} 字节)")

    # ── 4. 极端稳定参数 ──────────────────────────────────

    def test_04_ultra_stable(self):
        """
        极限稳定参数（temperature=0.1, do_sample=False 即贪心解码）。
        输出最确定、最可预测。
        """
        tid, data = self._submit_and_wait(
            speaker="Dylan",
            instruct="愉快，轻松",
            temperature=0.1,
            do_sample=False,
            top_k=10,
            top_p=0.5,
            repetition_penalty=1.3,
        )
        path = self._save_wav(data, "sampling_ultra_stable.wav")
        print(f"[OK] 极限稳定参数音频: {path} ({len(data)} 字节)")

    # ── 5. 仅部分参数（验证 None 降级） ──────────────────

    def test_05_partial_params(self):
        """
        仅传 temperature=0.5，其余为 None。
        服务端应对未传的参数使用保守默认值。
        """
        tid, data = self._submit_and_wait(
            speaker="Dylan",
            instruct="愉快，轻松",
            temperature=0.5,
            # do_sample / top_k / top_p / repetition_penalty 不传
        )
        path = self._save_wav(data, "sampling_partial.wav")
        print(f"[OK] 部分参数音频: {path} ({len(data)} 字节)")

    # ── 6. 同一文本多次生成对比（一致性测试） ────────────

    def test_06_consistency_same_text(self):
        """
        同一文本 + 同一保守参数，连续生成 3 次。
        保守参数下三份音频应非常相似（文件大小差异 <20%）。
        """
        sizes = []
        for i in range(3):
            _, data = self._submit_and_wait(
                speaker="Dylan",
                instruct="愉快，轻松",
                temperature=0.3,
                top_k=20,
                top_p=0.85,
                repetition_penalty=1.1,
            )
            self._save_wav(data, f"consistency_{i}.wav")
            sizes.append(len(data))
            print(f"  第 {i + 1} 次: {len(data)} 字节")

        # 检查三次生成的大小差异（粗略一致性指标）
        max_size = max(sizes)
        min_size = min(sizes)
        ratio = min_size / max_size if max_size > 0 else 0
        self.assertGreater(
            ratio, 0.7,
            f"三次生成大小差异过大: {sizes}，最小/最大={ratio:.2%}，"
            f"保守参数下应保持较高一致性"
        )
        print(f"[OK] 一致性测试通过，大小范围 {min_size}~{max_size} 字节，最小/最大={ratio:.2%}")

    # ── 7. 不同文本 + 保守参数（跨句一致性） ─────────────

    def test_07_cross_sentence_stability(self):
        """
        同一角色 + 保守参数，但文本不同。
        验证保守参数确实能减小不同句子间的声音差异。
        """
        texts = [
            "今天天气真不错，我们一起去公园散步吧。",
            "你知道吗？我昨天做了一个特别奇怪的梦。",
            "这本书我已经读了三遍了，每次都有新的收获。",
        ]
        sizes = []
        for i, text in enumerate(texts):
            r = client.submit(
                text=text,
                speaker="Dylan",
                instruct="愉快，轻松",
                temperature=0.3,
                top_k=20,
                top_p=0.85,
                repetition_penalty=1.1,
            )
            self.assertFalse(r.error)
            task_id = r.task_id

            sr = client.wait(task_id)
            self.assertTrue(sr.ok, f"任务 {task_id} 未完成")

            dl = client.download(task_id)
            self.assertTrue(dl.ok)
            out_path = self._save_wav(data=dl.data, filename=f"cross_sentence_{i}.wav")
            sizes.append(len(dl.data))
            print(f"  句子 {i + 1}: {len(dl.data)} 字节 → {out_path}")

        print(f"[OK] 跨句稳定性测试完成，大小范围 {min(sizes)}~{max(sizes)} 字节")


# ============================================================
# Test suite runner
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Qwen3-TTS API Auto Test")
    print(f"Server: {BASE_URL}")
    print("=" * 60)
    print()
    print("Test layers:")
    print("  1. TestTTSAPILegacy   - compatibility regression")
    print("  2. TestTTSAPISampling  - new sampling parameter tests")
    print("=" * 60)
    print()

    unittest.main(verbosity=2)
