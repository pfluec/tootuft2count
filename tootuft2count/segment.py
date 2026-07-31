# Updated segment.py with flexible model loading support
import os
import tifffile as tiff
import numpy as np


def segment_images(input_path, output_path, model_dir=None, method="instanseg", filenames=None, pixel_size=None):
    """
    Performs segmentation on multi-channel TIFF images using InstanSeg.

    Arguments:
    - input_path: folder containing .tiff images
    - output_path: folder to save segmentation masks
    - model_dir: optional path to pretrained model directory
    - method: 'instanseg' or 'cellpose'; determines which segmentation engine is used

    Output:
    - Label images saved as TIFFs in output_path, one per input.
    """
    os.makedirs(output_path, exist_ok=True)

    def list_tiff_files(folder_path):
        return sorted(f for f in os.listdir(folder_path) if f.lower().endswith(('.tif', '.tiff')))

    img_list = filenames or list_tiff_files(input_path)

    if method == "instanseg":
        from instanseg import InstanSeg
        model_path = model_dir if model_dir else "fluorescence_nuclei_and_cells"
        instanseg = InstanSeg(model_path, image_reader='skimage.io', verbosity=0)

        for image in img_list:
            image_path = os.path.join(input_path, image)
            print(f"Segmenting: {image}")

            kwargs = dict(image=image_path, save_output=False, save_overlay=False)
            if pixel_size is not None:
                kwargs["pixel_size"] = pixel_size
            labeled_output = instanseg.eval(**kwargs)
            cell_labels = labeled_output[0, 1].cpu().numpy()  # Validate if this index is still correct
            tiff.imwrite(os.path.join(output_path, image), cell_labels)



    elif method == "cellpose":
        from cellpose import models
        model = models.CellposeModel(gpu=True, pretrained_model=model_dir if model_dir else None)

        for image in img_list:
            image_path = os.path.join(input_path, image)
            img_data = tiff.imread(image_path)
            if img_data.ndim == 3:
                img_data = np.moveaxis(img_data, 0, -1)
            channels = [0, 0]  # customize as needed
            masks, _, _, _ = model.eval(img_data, channels=channels, diameter=None)
            tiff.imwrite(os.path.join(output_path, image), masks.astype(np.uint16))

    else:
        raise ValueError("Unsupported method. Choose 'instanseg' or 'cellpose'.")

    print("Segmentation complete.")
