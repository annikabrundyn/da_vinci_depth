# DaVinci Depth Map + Stereo View Prediction

# Overview

### data.py

This is where the DaVinciDataModule is defined. 

### model.py

This is the left view only model


### lr_model.py

This is the upper bound model that uses both left + right view as input


### unet.py

This is just the UNet architecture that is used in the two different models