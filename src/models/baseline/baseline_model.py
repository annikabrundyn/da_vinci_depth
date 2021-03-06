import pytorch_lightning as pl
import sys
import torch
import torch.nn as nn

from collections import defaultdict
from tqdm import tqdm

from argparse import ArgumentParser
from deprecated.data import DaVinciDataModule
from losses.loss_registry import LossRegistry


class BaselineModel(nn.Module):
    SUPPORTED_FILLS = {"zeros", "roll", "copy_left"}

    def __init__(self):
        super(BaselineModel, self).__init__()

    def forward(self, x, x_trans, fill="copy_left"):
        orig_x = torch.clone(x)
        out = torch.roll(x, x_trans, 2)
        img_width = x.size()[3]

        if x_trans <= 0:
            empty_slice_start = img_width + x_trans
            empty_slice_end = img_width
        else:
            empty_slice_start = 0
            empty_slice_end = img_width - x_trans

        if fill == "zeros":
            out[:, :, :, empty_slice_start:empty_slice_end] = 0
        elif fill == "copy_left":
            out[:, :, :, empty_slice_start:empty_slice_end] = orig_x[:, :, :,
                                                                     empty_slice_start:empty_slice_end]
        elif "roll":
            pass
        else:
            raise RuntimeError("Unsupported fill operation")

        return out


if __name__ == "__main__":
    # sets seed for numpy, torch, python.random and PYTHONHASHSEED
    pl.seed_everything(42)

    parser = ArgumentParser()
    parser.add_argument("--data_dir", type=str, help="path to davinci data")

    args = parser.parse_args()

    # CUDA for PyTorch
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if use_cuda else "cpu")

    # data
    dm = DaVinciDataModule(data_dir=args.data_dir, frames_per_sample=1,
                           frames_to_drop=0, num_workers=16)
    dm.setup()
    val_dataloader = dm.val_dataloader()
    sample_img = next(iter(val_dataloader))[0][0]

    # sanity check
    print("size of trainset:", len(dm.train_samples))
    print("size of validset:", len(dm.val_samples))
    print("size of testset:", len(dm.test_samples))

    # model
    model = BaselineModel().to(device)
    model.eval()

    loss_module_dict = {}
    loss_result_dict = defaultdict(lambda: defaultdict(float))
    losses_registry = LossRegistry.get_registry()
    print(losses_registry)

    # Instatiate each loss
    for loss in losses_registry:
        loss_module_dict[loss] = losses_registry[loss]().to(device)

    # Candidate x-coord shifts for input imgs
    img_width = len(sample_img[0][0])
    half_width = int(img_width / 2)
    translations = range(-half_width, half_width)

    # Train
    with torch.no_grad():
        for x_tran in tqdm(translations):
            for batch_idx, sample in enumerate(val_dataloader):
                inputs, targets = sample
                inputs, targets = inputs.squeeze(1).to(device), targets.to(device)
                shifted_inputs = model(inputs, x_tran)

                for loss in loss_module_dict:
                    loss_result_dict[loss][x_tran] += loss_module_dict[loss](
                        y_true=targets.to(device), y_pred=shifted_inputs).cpu().item() / len(inputs)

            for loss in loss_module_dict:
                loss_module_dict[loss].reset()

            if x_tran == -188:
                break

        torch.cuda.empty_cache()

    # Get min loss value and corresponding disparity for each loss
    final_results_dict = {}
    for loss in loss_result_dict:
        min_x_trans = min(loss_result_dict[loss], key=loss_result_dict[loss].get)
        min_loss = loss_result_dict[loss][min_x_trans]
        final_results_dict[loss] = {"min_loss": min_loss, "min_x_trans": min_x_trans}

    # Write results to file
    with open("baseline_results.txt", "w") as f:
        sys.stdout = f  # Change the standard output to the file we created.
        print(f"{final_results_dict}")
