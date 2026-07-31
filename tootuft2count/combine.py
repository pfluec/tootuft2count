import os
import glob
import tifftools


def combine_channels(main_directory, output_directory):
    """
    Combines individual single-channel TIFF files into stacked multi-channel TIFFs.

    Expects TIFF filenames to end with a channel index like 'ch0.tif', 'ch1.tif', etc.
    Filenames are grouped by shared prefix, and channels are stacked based on channel index.
    """

    main_directory = os.path.abspath(main_directory)
    output_directory = os.path.abspath(output_directory)
    tif_files = glob.glob(os.path.join(main_directory, '**', '*.tif'), recursive=True)
    if not tif_files:
        print("No TIFF files found in the specified input directory.")
        return

    image_paths_dict = {}
    for file_path in tif_files:
        base_name = os.path.splitext(os.path.basename(file_path))[0][:-4]
        relative_dir = os.path.dirname(os.path.relpath(file_path, main_directory))
        relative_key = os.path.join(relative_dir, base_name)
        image_paths_dict.setdefault(relative_key, []).append(file_path)

    def sort_key(path):
        filename = os.path.basename(path)
        return int(filename.split('ch')[-1].split('.')[0])

    for relative_key, paths in image_paths_dict.items():
        paths.sort(key=sort_key)
        relative_dir = os.path.dirname(relative_key)
        output_subdir = os.path.join(output_directory, relative_dir)
        os.makedirs(output_subdir, exist_ok=True)
        output_path = os.path.join(output_subdir, f"{os.path.basename(relative_key)}_combined.tiff")
        tifftools.tiff_concat(paths, output_path)

    print("Images combined and saved successfully!")