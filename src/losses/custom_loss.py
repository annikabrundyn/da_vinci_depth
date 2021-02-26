import torch
from torch import nn

from losses.perceptual_loss import Perceptual
from pytorch_lightning.metrics import SSIM


class L1_Perceptual(nn.Module):
    def __init__(self) -> None:
        '''
        Equal weight for L1 + Perceptual Loss
        '''
        super().__init__()
        self.l1 = nn.L1Loss()
        self.perceptual = Perceptual()

    def forward(self, y_true: torch.Tensor, y_pred: torch.Tensor) -> torch.Tensor:
        return self.l1(y_true, y_pred) + self.perceptual(y_true, y_pred)


class L1_SSIM(nn.Module):
    def __init__(self) -> None:
        '''
        Equal weight for L1 + SSIM
        '''
        super().__init__()
        self.l1 = nn.L1Loss()
        self.ssim = SSIM()

    def forward(self, y_true: torch.Tensor, y_pred: torch.Tensor) -> torch.Tensor:
        return self.l1(y_true, y_pred) + self.ssim(y_true, y_pred)