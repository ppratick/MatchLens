from __future__ import annotations

import cv2
import numpy as np
import onnxruntime as ort

from .domain import Detection

ort.disable_telemetry_events()


def shirt_color(image, box):
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box
    a, b = int(max(0, x1) * width), int(min(1, x2) * width)
    c, d = int(max(0, y1 + (y2 - y1) * 0.2) * height), int(min(1, y1 + (y2 - y1) * 0.55) * height)
    region = image[c:d, a:b]
    if region.size < 12:
        return None
    return np.median(region.reshape(-1, 3), axis=0).tolist()


class YOLOX:
    name = "yolox-tiny-onnx"

    def __init__(self, path, provider="CPUExecutionProvider", profile_path=None):
        import time

        if provider not in ort.get_available_providers():
            raise ValueError(f"Execution provider unavailable: {provider}")
        started = time.monotonic()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 3
        options.inter_op_num_threads = 1
        if profile_path:
            options.enable_profiling = True
            options.profile_file_prefix = str(profile_path)
        self.requested_provider = provider
        providers = (
            [
                (
                    provider,
                    {"ModelFormat": "MLProgram", "MLComputeUnits": "ALL", "RequireStaticInputShapes": "1"},
                ),
                "CPUExecutionProvider",
            ]
            if provider == "CoreMLExecutionProvider"
            else [provider]
        )
        self.session = ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=providers,
        )
        if provider not in self.session.get_providers():
            raise ValueError(f"{provider} initialization fell back; it is not executing as requested")
        self.initialization_seconds = time.monotonic() - started
        self.input = self.session.get_inputs()[0]
        self.height, self.width = (int(self.input.shape[-2]), int(self.input.shape[-1]))
        grids, strides = [], []
        for stride in (8, 16, 32):
            y, x = np.meshgrid(
                np.arange(self.height // stride), np.arange(self.width // stride), indexing="ij"
            )
            grid = np.stack((x, y), axis=2).reshape(-1, 2)
            grids.append(grid)
            strides.append(np.full((len(grid), 1), stride))
        self.grid, self.strides = np.concatenate(grids), np.concatenate(strides)

    def tensor(self, image):
        h, w = image.shape[:2]
        ratio = min(self.height / h, self.width / w)
        resized = cv2.resize(image, (int(w * ratio), int(h * ratio)))
        tensor = np.full((self.height, self.width, 3), 114, dtype=np.uint8)
        tensor[: resized.shape[0], : resized.shape[1]] = resized
        tensor = np.ascontiguousarray(tensor.transpose(2, 0, 1)[None], dtype=np.float32)
        return tensor, ratio

    def raw(self, image):
        tensor, _ = self.tensor(image)
        return self.session.run(None, {self.input.name: tensor})[0]

    def detect(self, image) -> list[Detection]:
        h, w = image.shape[:2]
        tensor, ratio = self.tensor(image)
        output = self.session.run(None, {self.input.name: tensor})[0][0].copy()
        if len(output) != len(self.grid):
            raise ValueError("Model output is not the supported raw YOLOX export")
        output[:, :2] = (output[:, :2] + self.grid) * self.strides
        output[:, 2:4] = np.exp(np.clip(output[:, 2:4], -20, 20)) * self.strides
        boxes = (
            np.concatenate((output[:, :2] - output[:, 2:4] / 2, output[:, :2] + output[:, 2:4] / 2), axis=1)
            / ratio
        )
        result = []
        for label, class_id in (("person", 0), ("ball", 32)):
            scores = output[:, 4] * output[:, 5 + class_id]
            keep = scores > (0.12 if label == "person" else 0.25)
            candidates, values = boxes[keep], scores[keep]
            xywh = candidates.copy()
            xywh[:, 2:] -= xywh[:, :2]
            indexes = cv2.dnn.NMSBoxes(xywh.tolist(), values.tolist(), 0.1, 0.5)
            for idx in np.asarray(indexes).reshape(-1):
                box = np.clip(candidates[idx] / [w, h, w, h], 0, 1).tolist()
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                result.append(
                    Detection(
                        box=box,
                        score=float(values[idx]),
                        kind=label,
                        color=shirt_color(image, box) if label == "person" else None,
                    )
                )
        return result


class HOG:
    name = "opencv-hog-baseline"

    def __init__(self):
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, image):
        h, w = image.shape[:2]
        scale = min(1.0, 960 / w)
        scaled = cv2.resize(image, (max(64, int(w * scale)), max(128, int(h * scale))))
        boxes, weights = self.hog.detectMultiScale(scaled, winStride=(8, 8), padding=(8, 8), scale=1.05)
        sh, sw = scaled.shape[:2]
        return [
            Detection(
                box=[x / sw, y / sh, (x + bw) / sw, (y + bh) / sh],
                score=float(np.clip(score / 3, 0.1, 1)),
                kind="person",
            )
            for (x, y, bw, bh), score in zip(boxes, weights)
        ]


class SyntheticDetector:
    """Only for the explicit generated demo, never selected for user footage."""

    name = "synthetic-color-fixture"

    def detect(self, image):
        h, w = image.shape[:2]
        result = []
        for low, high in (([0, 0, 150], [100, 120, 255]), ([150, 0, 0], [255, 150, 120])):
            mask = cv2.inRange(image, np.array(low, np.uint8), np.array(high, np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, bw, bh = cv2.boundingRect(contour)
                if 30 < bw * bh < 2500:
                    box = [x / w, y / h, (x + bw) / w, (y + bh) / h]
                    result.append(Detection(box=box, score=1.0, color=shirt_color(image, box)))
        return result


def detector_for(name, settings, provider="cpu", profile_path=None):
    if name in ("yolox", "yolox_s"):
        path = settings.data_dir / ("models/yolox_s.onnx" if name == "yolox_s" else "models/yolox_tiny.onnx")
        if not path.exists():
            raise ValueError(
                "YOLOX model missing. Run matchlens model install, or choose the limited HOG baseline."
            )
        model = YOLOX(
            path, "CoreMLExecutionProvider" if provider == "coreml" else "CPUExecutionProvider", profile_path
        )
        model.name = "yolox-small-onnx" if name == "yolox_s" else "yolox-tiny-onnx"
        return model
    if provider != "cpu":
        raise ValueError("CoreML execution is available only for ONNX detector adapters")
    if name == "hog":
        return HOG()
    if name == "synthetic":
        return SyntheticDetector()
    raise ValueError("Unknown detector")
