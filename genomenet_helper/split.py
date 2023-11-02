import os
import random
import shutil
import hashlib
import statistics

from .utils import generate_output_directory

def check_empty_files(dirs):
    """
    Check if any file in the directories is empty.
    Returns a list of empty files.
    """
    empty_files = []
    for d in dirs:
        for file in os.listdir(d):
            if os.path.getsize(os.path.join(d, file)) == 0:
                empty_files.append(os.path.join(d, file))
    return empty_files

def file_size_outliers(dirs):
    """
    Checks for file size outliers, which are defined as files that have a size 2 SDs away from the mean.
    Returns the average file size and a list of outlier files.
    """
    file_sizes = []
    for d in dirs:
        for file in os.listdir(d):
            file_sizes.append(os.path.getsize(os.path.join(d, file)))

    mean_size = statistics.mean(file_sizes)
    stdev_size = statistics.stdev(file_sizes)
    outliers = [os.path.join(d, file) for d in dirs for file in os.listdir(d) if abs(os.path.getsize(os.path.join(d, file)) - mean_size) > 2 * stdev_size]
    return mean_size, outliers

def rename_files(input_dir):
    files_to_rename = [f for f in os.listdir(input_dir) if f.endswith('.fna')]
    for f in files_to_rename:
        os.rename(os.path.join(input_dir, f), os.path.join(input_dir, f.replace('.fna', '.fasta')))

def contains_non_acgt(filename):
    """
    Check if a FASTA file contains non-ACGT characters.
    """
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()  # Remove any trailing whitespace
            if not line:  # Skip empty lines
                continue
            if line.startswith('>'):  # Skip FASTA header lines
                continue
            for char in line:
                if char not in 'ACGTNacgtn':  # Considering both uppercase and lowercase characters
                    return True
    return False

def check_duplicate_filenames(dirs):
    all_files = []
    for d in dirs:
        all_files.extend(os.listdir(d))
    return len(all_files) != len(set(all_files))

def compute_hash(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def check_file_hashes(dirs):
    hashes = {}
    for d in dirs:
        for file in os.listdir(d):
            file_hash = compute_hash(os.path.join(d, file))
            if file_hash in hashes:
                return False, (hashes[file_hash], os.path.join(d, file))
            hashes[file_hash] = os.path.join(d, file)
    return True, None

def get_file_sizes(input_dir):
    """
    Returns a dictionary with file names as keys and their sizes as values.
    """
    return {f: os.path.getsize(os.path.join(input_dir, f)) for f in os.listdir(input_dir) if f.endswith('.fasta')}

def split_files_by_size(file_sizes, fractions):
    """
    Splits the files based on their sizes according to the given fractions.
    """
    total_size = sum(file_sizes.values())
    sorted_files = sorted(file_sizes.keys(), key=lambda x: file_sizes[x], reverse=True)

    train_size = fractions[0] / 100 * total_size
    val_size = fractions[1] / 100 * total_size

    train_files, val_files, test_files = [], [], []
    current_train, current_val = 0, 0

    for f in sorted_files:
        if current_train + file_sizes[f] <= train_size:
            train_files.append(f)
            current_train += file_sizes[f]
        elif current_val + file_sizes[f] <= val_size:
            val_files.append(f)
            current_val += file_sizes[f]
        else:
            test_files.append(f)

    return train_files, val_files, test_files

import shutil

def split_files(input_dir, fractions, by_size=False):
    """
    Splits the files in input_dir according to the given fractions.
    """
    output_dir_base = os.path.basename(os.path.normpath(input_dir))
    all_files = [f for f in os.listdir(input_dir) if f.endswith('.fasta')]

    # Check for non-fasta files
    non_fasta_files = [f for f in os.listdir(input_dir) if not f.endswith('.fasta')]
    if non_fasta_files:
        raise ValueError("Found non-fasta files: " + ", ".join(non_fasta_files))

    # Check and rename .fna files
    fna_files = [f for f in os.listdir(input_dir) if f.endswith('.fna')]
    if fna_files:
        rename_choice = input("Found .fna files. Do you want to rename them to .fasta? (y/n): ")
        if rename_choice.strip().lower() == 'y':
            rename_files(input_dir)
        
    amino_files = []
    print("Reading file informations")
    for file in os.listdir(input_dir):
        if file.endswith('.fasta'):
            filepath = os.path.join(input_dir, file)
            if contains_non_acgt(filepath):
                amino_files.append(filepath)

    if amino_files:
        print("Warning: The following files seem to contain non-ACGT characters (possible amino acid sequences):")
        for f in amino_files:
            print(f)

    if by_size:
        file_sizes = get_file_sizes(input_dir)
        train_files, val_files, test_files = split_files_by_size(file_sizes, fractions)
    else:
        random.shuffle(all_files)
        n = len(all_files)
        train_files = all_files[:int(n * fractions[0] / 100)]
        val_files = all_files[int(n * fractions[0] / 100):int(n * (fractions[0] + fractions[1]) / 100)]
        test_files = all_files[int(n * (fractions[0] + fractions[1]) / 100):]

    dirs = ["train", "validation", "test"]
    output_dirs = []   # <-- Initialize here
    for d, files in zip(dirs, [train_files, val_files, test_files]):
        output_dir = generate_output_directory(input_dir, d)
        output_dirs.append(output_dir)  # <-- Add to the list here
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for f in files:
            shutil.copy2(os.path.join(input_dir, f), os.path.join(output_dir, f))
        print(f"{output_dir} contains {len(files)} files with a total size of {sum([os.path.getsize(os.path.join(output_dir, x)) for x in files]) / (1024 * 1024 * 1024):.2f} GB")

    delete_original = input("Do you want to delete the original files in the source directory? (y/n): ")
    if delete_original.strip().lower() == 'y':
        for f in all_files:
            os.remove(os.path.join(input_dir, f))
        print(f"Original files in {input_dir} have been deleted.")

    
    # test if there are files with a unexpected size
    mean_size, outlier_files = file_size_outliers(output_dirs)
    if outlier_files:
        print(f"\nAverage file size is {mean_size / (1024 * 1024):.2f} MB.")
        print(f"{len(outlier_files)} files are significantly larger or smaller than the average:")
        for f in outlier_files:
            print(f"{f} - {os.path.getsize(f) / (1024 * 1024):.2f} MB")
    else:
        print("\nAll files are of typical size. No outliers detected.")

    # Check for duplicate filenames
    output_dirs = [generate_output_directory(input_dir, d) for d in ["train", "validation", "test"]]
    if check_duplicate_filenames(output_dirs):
        raise ValueError("Duplicate filenames detected across train, validation, and test folders!")

    # Check for file content duplication using hashes
    hash_check_choice = input("Do you want to check for duplicate content across files using hashes? (y/n): ")
    if hash_check_choice.strip().lower() == 'y':
        success, duplicate_files = check_file_hashes(output_dirs)
        if not success:
            print(f"Files {duplicate_files[0]} and {duplicate_files[1]} have the same content!")
        else:
             print("No duplications found.")

    # check for empty files
    empty_files = check_empty_files(output_dirs)
    if empty_files:
        print("Warning: The following files are empty:")
        for f in empty_files:
            print(f)
    else:
        print("All files have content. None are empty.")
