# @formatter:off

import hashlib
import os
import xlsxwriter
import datetime
import sys
import argparse
import requests
import subprocess
from tqdm import tqdm

verbose_logging = False
log = None
max_retries = 5


class CustomLogger:
    def __init__(self, log_file, save_to_file=True):
        self.log_file = log_file
        self.save_to_file = save_to_file

    def log(self, message, context="INFO", level="INFO"):
        log_message = f"{context} - {message}"

        if level == "ERROR":
            print("\033[91m" + log_message + "\033[0m")
        elif level == "WARNING":
            print("\033[93m" + log_message + "\033[0m")
        else:
            print(log_message)

        if self.save_to_file:
            with open(self.log_file, 'a') as f:
                f.write(log_message + '\n')


def get_hash(file_path, hash_algorithm):
    hasher = hashlib.new(hash_algorithm)
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
            yield hasher.hexdigest()
            if verbose_logging:
                log.log(f"{file_path} - {hasher.hexdigest()}", context="INFO", level="INFO")


def get_all_hashes(file_path):
    hash_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
    hashes = {}
    for algorithm in hash_algorithms:
        hash_generator = get_hash(file_path, algorithm)
        file_hash = next(hash_generator)
        hashes[algorithm] = file_hash
        if verbose_logging:
            log.log(f"{file_path} - {file_hash}", context="INFO", level="INFO")
    return hashes


def confirm_action(message):
    while True:
        user_input = input(f"{message} (y/n): ").lower()
        if user_input in ['y', 'n']:
            return user_input == 'y'


def format_file_size(size_in_bytes):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024
        unit_index += 1
    return f"{size_in_bytes:.2f} {units[unit_index]}"


def generate_spreadsheet(workbook, worksheet, hash_algorithms):
    headers = ["File Name", "File Path", "Size of File", "Date Created", "Date Modified"]
    headers.extend([f"File Hash ({algorithm.upper()})" for algorithm in hash_algorithms])

    bold = workbook.add_format({'bold': True})
    worksheet.write_row(0, 0, headers, bold)

    worksheet.set_column('A:A', 30)  # File Name
    worksheet.set_column('B:B', 50)  # File Path
    worksheet.set_column('C:C', 15)  # Size of File
    worksheet.set_column('D:D', 20)  # Date Created
    worksheet.set_column('E:E', 20)  # Date Modified
    if len(hash_algorithms) > 1:
        for col_idx in range(5, len(headers)):
            col_letter = chr(ord('C') + col_idx - 2)
            worksheet.set_column(f'{col_letter}:{col_letter}', 75)


def compare_directories(worksheet, hash_algorithms, workbook):
    headers = ["Matching"]
    headers.extend([f"File Hash ({algorithm.upper()})" for algorithm in hash_algorithms])
    bold = workbook.add_format({'bold': True})
    worksheet.write_row(0, 0, headers, bold)


def gen_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes):
    report = "\n---START OF REPORT---\n\n"
    report += f"Directory: {directory}\n"
    report += f"Algorithm: {'All' if all_hashes else hash_option.upper()}\n"
    report += f"Successful Hashes: {successful_hashes}\n"
    report += f"Failed Hashes: {failed_hashes}\n\n"

    report += "Hashed Files:\n"
    for name, path in hashed_files:
        report += f"{name} | {path}\n"

    report += "\nFile Hashes:\n"
    report += list_of_hashes

    report += f"\nStart Time: {start_time}\n"
    report += f"End Time: {end_time}\n"

    time_taken = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
    report += f"Time Taken: {time_taken}\n\n"
    report += "---END OF REPORT---\n"

    with open('hashes_report.txt', 'w') as report_file:
        report_file.write(report)


def generate_comparison_report(directory1, directory2, matching_files, unmatching_files, start_time, end_time):
    report = "\n---START OF COMPARISON REPORT---\n\n"
    report += f"Directory 1: {directory1}\n"
    report += f"Directory 2: {directory2}\n\n"

    report += f"Matching: {len(matching_files)}\n"
    report += f"Not Matching: {len(unmatching_files)}\n\n"

    report += f"Quick Summary: ({len(matching_files)}/{len(matching_files) + len(unmatching_files)}) files are matching\n\n"

    report += "Matching Files:\n"
    for name in matching_files:
        report += f"{name}\n"

    report += "\nUnmatching Files:\n"
    for name in unmatching_files:
        report += f"{name}\n"

    report += f"\nStart Time: {start_time}\n"
    report += f"End Time: {end_time}\n"

    time_taken = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
    report += f"Time Taken: {time_taken}\n\n"

    report += "---END OF COMPARISON REPORT---\n"

    with open('comparison_report.txt', 'w') as report_file:
        report_file.write(report)


def compare_versions(version1, version2):
    v1_numbers = list(map(int, version1.split('.')))
    v2_numbers = list(map(int, version2.split('.')))

    for v1, v2 in zip(v1_numbers, v2_numbers):
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1

    if len(v1_numbers) > len(v2_numbers):
        return 1
    elif len(v1_numbers) < len(v2_numbers):
        return -1

    return 0


def check_for_updates(current_version):
    repo_url = "https://api.github.com/repos/AidenFliss/Hasher-Util/releases/latest"
    try:
        response = requests.get(repo_url)
        if response.status_code == 200:
            latest_release = response.json()
            latest_version = latest_release['tag_name'].replace('v', '')
            if latest_version and compare_versions(latest_version, current_version) > 0:
                log.log(f"An update is available! Current version: {current_version}, Latest version: {latest_version}", context="WARNING", level="WARNING")
                return latest_version
            else:
                log.log("\033[92m" + f"Your version ({current_version}) is up to date." + "\033[0m", context="INFO", level="INFO")
        else:
            log.log("\033[91m" + "Failed to fetch latest release information." + "\033[0m", context="ERROR", level="ERROR")
    except Exception as e:
        log.log("\033[91m" + f"Error checking for updates: {e}" + "\033[0m", context="ERROR", level="ERROR")
    return None


def download_update(update_url, latest_version):
    try:
        response = requests.get(update_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        with open(f'v{latest_version}-HasherUtil.exe', 'wb') as file:
            with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, ncols=100, ascii=False, dynamic_ncols=True, colour="blue") as bar:
                for data in response.iter_content(chunk_size=1024):
                    file.write(data)
                    bar.update(len(data))
                    sys.stdout.flush()
        return file.name, os.getcwd() + "\\" + file.name
    except Exception as e:
        log.log("\033[91m" + f"Error downloading update: {e}" + "\033[0m", context="ERROR", level="ERROR")
        return None


def update_and_restart(update_filepath):
    log.log("Updating...", context="INFO", level="INFO")
    subprocess.run(update_filepath)
    sys.exit()


def main():
    current_version = "1.0.2"

    global verbose_logging
    global log

    log = CustomLogger('output.log')

    parser = argparse.ArgumentParser(description="Hasher Utility Script")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-c", "--compare", action="store_true", help="Compare hashes of two directories (uses all algorithms)")
    parser.add_argument("-d1", "--dir1", help="Path of the first directory to compare")
    parser.add_argument("-d2", "--dir2", help="Path of the second directory to compare")
    parser.add_argument("-a", "--algorithm", help="Hash algorithm to use (md5, sha1, sha256, sha512)")
    parser.add_argument("-dir", "--directory", help="Path of the directory for single-folder hash generation")
    parser.add_argument("-g", "--generate", action="store_true", help="If a report and spreadsheet should be made")
    parser.add_argument("-s", "--skip-update", action="store_true", help="Skip automatic update check")
    parser.add_argument("-u", "--update", action="store_true", help="Forces an update if available")
    args = parser.parse_args()

    log.log(f"Bulk Hasher v{current_version}", context="INFO", level="INFO")
    log.log("Made by: Aiden Fliss", context="INFO", level="INFO")
    log.log("Command line args:", context="INFO", level="INFO")
    log.log("-v --verbose Enable verbose logging", context="INFO", level="INFO")
    log.log("-c --compare Compare hashes of two directories (uses all algorithms)", context="INFO", level="INFO")
    log.log("-d1 <path> --dir1 Path of the first directory to compare", context="INFO", level="INFO")
    log.log("-d2 <path> --dir2 Path of the second directory to compare", context="INFO", level="INFO")
    log.log("-a --algorithm <alg.> Hash algorithm to use (md5, sha1, sha256, sha512)", context="INFO", level="INFO")
    log.log("-dir <path> --directory Path of the directory for single-folder hash generation", context="INFO", level="INFO")
    log.log("-g --generate If a report and spreadsheet should be made", context="INFO", level="INFO")
    log.log("-s --skip-update Skip automatic update check", context="INFO", level="INFO")
    log.log("-u --update Forces an update if available\n", context="INFO", level="INFO")

    if not args.skip_update:
        try:
            latest_version = check_for_updates(current_version)
            if latest_version:
                if args.update or confirm_action("Do you want to download the latest update?"):
                    update_url = f"https://github.com/AidenFliss/Hasher-Util/releases/download/v{latest_version}/v{latest_version}-HasherUtil.exe"
                    update_filename, file_path = download_update(update_url, latest_version)
                    if update_filename is not None:
                        log.log(f"Update downloaded: {update_filename}")
                        update_and_restart(file_path)
                    else:
                        log.log(f"Error downloading update v{latest_version}", context="ERROR", level="ERROR")
                else:
                    log.log(f"Skipped update version: {latest_version} due to an error downloading!", context="WARNING", level="WARNING")
        except Exception as e:
            log.log(f"Error during update process: {e}", context="ERROR", level="ERROR")

    if args.verbose:
        verbose_logging = True

    if args.compare:
        compare_dirs = True
        if not args.dir1 or not args.dir2:
            log.log("Both directory paths are required for comparison.", context="ERROR", level="ERROR")
            sys.exit(1)

        dir1 = args.dir1
        dir2 = args.dir2

        if not os.path.isdir(dir1) or not os.path.isdir(dir2):
            log.log("Invalid directories. Please enter valid directory paths.", context="ERROR", level="ERROR")
            sys.exit(1)

        hash_info_list_dir1 = []
        hash_info_list_dir2 = []
        hash_info_dict = {}

        if args.generate:
            start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

        for root, _, files in os.walk(dir1):
            for file in files:
                file_path = os.path.join(root, file)
                retries = 0
                while retries < max_retries:
                    try:
                        hashes = get_all_hashes(file_path)
                        break
                    except Exception as e:
                        retries += 1
                        log.log(f"Error hashing {file_path}: {e}. Retrying... ({retries}/{max_retries})", context="ERROR", level="ERROR")
                        hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}
                else:
                    log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                hash_info_list_dir1.append((file, file_path, hashes))

        for root, _, files in os.walk(dir2):
            for file in files:
                file_path = os.path.join(root, file)
                retries = 0
                while retries < max_retries:
                    try:
                        hashes = get_all_hashes(file_path)
                        break
                    except Exception as e:
                        retries += 1
                        log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                        hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}
                else:
                    log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                hash_info_list_dir2.append((file, file_path, hashes))

        matching_files = []
        unmatching_files = []

        for name1, path1, hashes1 in hash_info_list_dir1:
            matching_info = "Not Matching"
            for name2, path2, hashes2 in hash_info_list_dir2:
                if name1 == name2:
                    if all(hashes1.get(algorithm) == hashes2.get(algorithm) for algorithm in ['md5', 'sha1', 'sha256', 'sha512']):
                        matching_info = "Matching"
                        matching_files.append(name1)
                    else:
                        unmatching_files.append(name1)
                    break
            hash_info_dict[name1] = (matching_info, path1, hashes1)

        if args.generate:
            end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            generate_comparison_report(dir1, dir2, matching_files, unmatching_files, start_time, end_time)

    if args.directory:
        directory = args.directory if args.directory else input("Enter the directory path: ")
        hash_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
        all_hashes = True if args.algorithm == 'all' else False

        while True:
            if args.algorithm:
                hash_option = args.algorithm
            else:
                hash_option = input("Choose a hash algorithm: ").lower() if not all_hashes else 'all'
            if not all_hashes and hash_option not in hash_algorithms:
                log.log("Invalid hash algorithm.", context="ERROR", level="ERROR")
                continue
            break

        successful_hashes = 0
        failed_hashes = 0
        hashed_files = []
        hash_info_dict = {}

        row = 0

        if args.generate:
            start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            workbook = xlsxwriter.Workbook('hashes.xlsx')
            worksheet = workbook.add_worksheet()
            generate_spreadsheet(workbook, worksheet, hash_algorithms)

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                retries = 0
                while retries < max_retries:
                    try:
                        if all_hashes:
                            hashes = get_all_hashes(file_path)
                        else:
                            hash_generator = get_hash(file_path, hash_option)
                            file_hash = next(hash_generator)
                            hashes = {hash_option: file_hash}
                            if verbose_logging:
                                log.log(f"{file_path} - {file_hash}", context="INFO", level="INFO")
                        break
                    except Exception as e:
                        retries += 1
                        log.log(f"Error hashing {file_path}: {e}. Retrying... ({retries}/{max_retries})", context="ERROR", level="ERROR")
                        hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}
                else:
                    log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                    failed_hashes += 1

                hashed_files.append((file, file_path))
                successful_hashes += 1

                log.log(f"{file_path}: {' '.join(hashes.values()) if all_hashes else file_hash}")

                if args.generate:
                    hash_info_dict[file] = (file_path, hashes)

                    row += 1
                    worksheet.write(row, 0, file)
                    worksheet.write(row, 1, file_path)
                    worksheet.write(row, 2, format_file_size(os.path.getsize(file_path)))
                    worksheet.write(row, 3, datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m/%d/%Y'))
                    worksheet.write(row, 4, datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m/%d/%Y'))

                    if len(hash_algorithms) == 1:
                        worksheet.write(row, 5, hashes[hash_option])
                    else:
                        col = 5
                        for algorithm in hash_algorithms:
                            worksheet.write(row, col, hashes.get(algorithm, "N/A"))
                            col += 1

        log.log("Finished hashing directory!", context="INFO", level="INFO")

        if args.generate:
            workbook.close()

            list_of_hashes = ""
            for name, (_, hashes) in hash_info_dict.items():
                hash_strings = " | ".join(f"{algorithm}: {hash}" for algorithm, hash in hashes.items())
                list_of_hashes += f"{name} | {hash_strings}\n"

            end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

            time_taken = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
            gen_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes)

            log.log("Hash report generated.", context="REPORT")

    if not args.verbose and not args.compare and not args.generate:
        generate_report = True

        while True:
            if confirm_action("Enable verbose logging (log hashed files)?"):
                verbose_logging = True
            if not confirm_action("Compare hashes of two directories?"):
                compare_dirs = False
            else:
                compare_dirs = True
                compare_dir_1 = input("Enter the path of the first directory: ")
                compare_dir_2 = input("Enter the path of the second directory: ")

                if not os.path.isdir(compare_dir_1) or not os.path.isdir(compare_dir_2):
                    log.log("Invalid directories. Please enter valid directory paths.", context="ERROR", level="ERROR")
                    continue

            if not confirm_action("Generate hash report and spreadsheet?"):
                generate_report = False

            if not compare_dirs:
                directory = input("Enter the directory path: ")
                if not os.path.isdir(directory):
                    log.log("Invalid directory. Please enter a valid directory path.", context="ERROR", level="ERROR")
                    continue

            while True:
                if not compare_dirs:
                    if not confirm_action("Calculate all available hash algorithms?"):
                        log.log("Available hash algorithms:", context="INFO", level="INFO")
                        log.log("1. md5\n2. sha1\n3. sha256\n4. sha512", context="INFO", level="INFO")
                        hash_option = input("Choose a hash algorithm: ").lower()
                        if hash_option not in ['md5', 'sha1', 'sha256', 'sha512']:
                            log.log("Invalid hash algorithm.", context="ERROR", level="ERROR")
                            continue
                    else:
                        hash_option = 'all'
                    break
                else:
                    hash_option = 'all'
                    break

            hash_algorithms = ['md5', 'sha1', 'sha256', 'sha512'] if hash_option == 'all' else [hash_option]
            all_hashes = True if hash_option == 'all' else False

            successful_hashes = 0
            failed_hashes = 0
            hashed_files = []
            hash_info_dict = {}

            row = 0

            if generate_report:
                start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                workbook = xlsxwriter.Workbook('hashes.xlsx')
                worksheet = workbook.add_worksheet()

                if compare_dirs:
                    compare_directories(worksheet, hash_algorithms, workbook)
                else:
                    generate_spreadsheet(workbook, worksheet, hash_algorithms)

            if compare_dirs:
                log.log("Comparing hashes of two directories...")
                hash_info_list_dir1 = []
                hash_info_list_dir2 = []

                for root, _, files in os.walk(dir1):
                    for file in files:
                        file_path = os.path.join(root, file)
                        retries = 0
                        while retries < max_retries:
                            try:
                                hashes = get_all_hashes(file_path)
                                break
                            except Exception as e:
                                retries += 1
                                log.log(f"Error hashing {file_path}: {e}. Retrying... ({retries}/{max_retries})", context="ERROR", level="ERROR")
                                hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}
                        else:
                            log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                        hash_info_list_dir1.append((file, file_path, hashes))

                for root, _, files in os.walk(dir2):
                    for file in files:
                        file_path = os.path.join(root, file)
                        retries = 0
                        while retries < max_retries:
                            try:
                                hashes = get_all_hashes(file_path)
                                break
                            except Exception as e:
                                retries += 1
                                log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                                hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}
                        else:
                            log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                        hash_info_list_dir2.append((file, file_path, hashes))

                if generate_report:
                    matching_files = []
                    unmatching_files = []

                    for name1, path1, hashes1 in hash_info_list_dir1:
                        matching_info = "Not Matching"
                        for name2, path2, hashes2 in hash_info_list_dir2:
                            if name1 == name2:
                                if all(hashes1.get(algorithm) == hashes2.get(algorithm) for algorithm in hash_algorithms):
                                    matching_info = "Matching"
                                    matching_files.append(name1)
                                else:
                                    unmatching_files.append(name1)
                                break
                        hash_info_dict[name1] = (matching_info, path1, hashes1)

                    end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                    generate_comparison_report(compare_dir_1, compare_dir_2, matching_files, unmatching_files, start_time, end_time)

                    log.log("Finished generating comparison report!", context="REPORT")

                log.log("Finished comparing directories!", context="REPORT")

            else:
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        retries = 0
                        while retries < max_retries:
                            try:
                                if all_hashes:
                                    hashes = get_all_hashes(file_path)
                                else:
                                    hash_generator = get_hash(file_path, hash_option)
                                    file_hash = next(hash_generator)
                                    hashes = {hash_option: file_hash}
                                    if verbose_logging:
                                        log.log(f"{file_path} - {file_hash}", context="INFO", level="INFO")
                                break
                            except Exception as e:
                                retries += 1
                                log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                                hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}
                        else:
                            log.log(f"Failed to hash {file_path} after {max_retries} retries.", context="ERROR", level="ERROR")
                            failed_hashes += 1

                        hashed_files.append((file, file_path))
                        successful_hashes += 1

                        log.log(f"{file_path}: {' '.join(hashes.values()) if all_hashes else file_hash}")

                        hash_info_dict[file] = (file_path, hashes)

                        if generate_report:
                            hash_info_dict[file] = (file_path, hashes)

                            row += 1
                            worksheet.write(row, 0, file)
                            worksheet.write(row, 1, file_path)
                            worksheet.write(row, 2, format_file_size(os.path.getsize(file_path)))
                            worksheet.write(row, 3, datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m/%d/%Y'))
                            worksheet.write(row, 4, datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m/%d/%Y'))

                            if len(hash_algorithms) == 1:
                                worksheet.write(row, 5, hashes[hash_option])
                            else:
                                col = 5
                                for algorithm in hash_algorithms:
                                    worksheet.write(row, col, hashes.get(algorithm, "N/A"))
                                    col += 1

                if generate_report:
                    workbook.close()

                    list_of_hashes = ""
                    for name, (_, hashes) in hash_info_dict.items():
                        hash_strings = " | ".join(f"{algorithm}: {hash}" for algorithm, hash in hashes.items())
                        list_of_hashes += f"{name} | {hash_strings}\n"

                        end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

                        time_taken = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
                        gen_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes)

                    log.log("Hash report generated.", context="REPORT")

                log.log("Finished hashing directory!", context="REPORT")

            if confirm_action("Do you want to quit?"):
                sys.exit(0)


if __name__ == "__main__":
    main()
