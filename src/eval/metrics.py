"""评估指标：RMSE 与归一化 RMSE（赛题 Card 评分同款口径）"""
import numpy as np


def rmse(pred: np.ndarray, target: np.ndarray) -> float:
    pred, target = np.asarray(pred, float), np.asarray(target, float)
    return float(np.sqrt(np.mean((pred - target) ** 2)))


def nrmse(pred: np.ndarray, target: np.ndarray) -> float:
    """归一化 RMSE：除以目标峰值。越小越好，0 = 完美贴合。"""
    return rmse(pred, target) / float(np.abs(target).max())
