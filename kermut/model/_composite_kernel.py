from typing import Tuple, Literal

import hydra
from gpytorch.constraints import Interval
from gpytorch.kernels import ScaleKernel
from gpytorch import Module
from omegaconf import DictConfig
import torch
from torch import Tensor, LongTensor

from ._structure_kernel import StructureKernel
from ._sequence_kernel import SequenceKernel


class CompositeKernel(Module):
    """TODO"""

    def __init__(
        self,
        structure_kernel: DictConfig,
        sequence_kernel: DictConfig,
        composition: Literal["weighted_sum", "add", "multiply"] = "weighted_sum",
        **kwargs,
    ):
        super().__init__()

        self.structure_kernel: StructureKernel = hydra.utils.instantiate(
            structure_kernel, **kwargs
        )
        self.sequence_kernel: SequenceKernel = hydra.utils.instantiate(sequence_kernel)

        self.composition = composition
        match composition:
            case "weighted_sum":
                # This formulation follows NeurIPS manuscript.
                self.register_parameter("pi", torch.nn.Parameter(torch.tensor(0.5)))
                self.register_constraint("pi", Interval(0, 1))
                self.structure_kernel = ScaleKernel(self.structure_kernel)
            case "add":
                self.structure_kernel = ScaleKernel(self.structure_kernel)
                self.sequence_kernel = ScaleKernel(self.sequence_kernel)
            case "multiply":
                self.scale_kernel = ScaleKernel()

    def forward(
        self,
        x1: Tuple[LongTensor, Tensor],
        x2: Tuple[LongTensor, Tensor] = None,
        **params,
    ) -> Tensor:

        if x2 is None:
            x2 = x1

        x1_toks, x1_emb = x1
        x2_toks, x2_emb = x2

        match self.composition:
            case "weighted_sum":
                return self.structure_kernel(
                    x1_toks, x2_toks, **params
                ) * self.pi + self.sequence_kernel(x1_emb, x2_emb, **params) * (
                    1 - self.pi
                )
            case "add":
                return self.structure_kernel(
                    x1_toks, x2_toks, **params
                ) + self.sequence_kernel(x1_emb, x2_emb, **params)
            case "multiply":
                return self.scale_kernel(
                    self.structure_kernel(x1_toks, x2_toks, **params)
                    * self.sequence_kernel(x1_emb, x2_emb, **params)
                )
