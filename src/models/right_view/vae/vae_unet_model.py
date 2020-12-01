import torch
import torch.nn.functional as F
import pytorch_lightning as pl

from argparse import ArgumentParser

from data.right_data import RightDaVinciDataModule
from pytorch_lightning.metrics.functional import ssim, psnr

from models.right_view.vae.vae_unet import VariationalUNet
from models.callbacks.vae_callback import VAERightCallback


class VAEModel(pl.LightningModule):
    def __init__(
            self,
            frames_per_sample: int = 1,
            frames_to_drop: int = 0,
            enc_out_dim: int = 128,
            latent_dim: int = 128,
            kl_coeff: float = 0.1,
            lr: float = 0.001,
            log_tb_imgs: bool = False,
            tb_img_freq: int = 10000,
            save_img_freq: int = 50,
            num_layers: int = 5,
            features_start: int = 64,
            bilinear: bool = False,
            **kwargs
    ):
        super().__init__()

        self.frames_per_sample = frames_per_sample
        self.frames_to_drop = frames_to_drop

        self.save_hyperparameters()

        # TODO: generalize for multi frame
        self.in_channels = 3

        self.net = VariationalUNet(input_channels=self.in_channels,
                                   output_channels=3,
                                   enc_out_dim=enc_out_dim,
                                   latent_dim=latent_dim,
                                   num_layers=num_layers,
                                   features_start=features_start,
                                   bilinear=bilinear)

    def forward(self, x):
        return self.net(x)

    def step(self, batch, batch_idx):
        img, target = batch
        pred, kl = self(img)

        mse_loss = F.mse_loss(pred, target)
        loss = mse_loss + kl

        ssim_val = ssim(pred, target)

        logs = {
            "mse_loss": mse_loss,
            "kl": kl,
            "loss": loss,
            "ssim": ssim_val
        }

        return loss, logs

    def training_step(self, batch, batch_idx):
        loss, logs = self.step(batch, batch_idx)
        self.log_dict({f"train_{k}": v for k, v in logs.items()})

        return loss

    def validation_step(self, batch, batch_idx):
        loss, logs = self.step(batch, batch_idx)
        self.log_dict({f"val_{k}": v for k, v in logs.items()})

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.lr)

    @staticmethod
    def add_model_specific_args(parent_parser):
        parser = ArgumentParser(parents=[parent_parser], add_help=False)
        parser.add_argument("--data_dir", type=str, default="/Users/annikabrundyn/Developer/da_vinci/daVinci_data", help="path to davinci data")
        parser.add_argument("--frames_per_sample", type=int, default=1, help="number of frames to include in each sample")
        parser.add_argument("--frames_to_drop", type=int, default=0, help="number of frames to randomly drop in each sample")
        parser.add_argument("--enc_out_dim", type=int, default=128)
        parser.add_argument("--latent_dim", type=int, default=128)
        parser.add_argument("--kl_coeff", type=float, default=0.1)
        parser.add_argument("--batch_size", type=int, default=16, help="size of the batches")
        parser.add_argument("--log_tb_imgs", action='store_true', default=False)
        parser.add_argument("--tb_img_freq", type=int, default=10000)
        parser.add_argument("--save_img_freq", type=int, default=50)
        parser.add_argument("--num_workers", type=int, default=8)
        parser.add_argument("--lr", type=float, default=0.001, help="adam: learning rate")
        parser.add_argument("--num_layers", type=int, default=5, help="number of layers on u-net")
        parser.add_argument("--features_start", type=float, default=64, help="number of features in first layer")
        parser.add_argument("--bilinear", action='store_true', default=False,
                            help="whether to use bilinear interpolation or transposed")

        return parser



if __name__ == "__main__":
    # sets seed for numpy, torch, python.random and PYTHONHASHSEED
    pl.seed_everything(42)

    parser = ArgumentParser()

    # trainer args
    parser = pl.Trainer.add_argparse_args(parser)

    # model args
    parser = VAEModel.add_model_specific_args(parser)
    args = parser.parse_args()

    # data
    dm = RightDaVinciDataModule(
        args.data_dir,
        frames_per_sample=1,
        frames_to_drop=0,
        is_color_input=True,
        is_color_output=True,
        extra_info=False,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )
    dm.setup()
    print("dm setup")

    # sanity check
    print("size of trainset:", len(dm.train_samples))
    print("size of validset:", len(dm.val_samples))
    print("size of testset:", len(dm.test_samples))

    img, target = next(iter(dm.train_dataloader()))
    print(img.shape)
    print(target.shape)

    # model
    model = VAEModel(**args.__dict__)
    print("model instance created")
    print("lightning version", pl.__version__)

    # train
    #trainer = pl.Trainer.from_argparse_args(args)
    trainer = pl.Trainer.from_argparse_args(args, callbacks = [VAERightCallback(args.save_img_freq)])
    print("trainer created")
    trainer.fit(model, dm)