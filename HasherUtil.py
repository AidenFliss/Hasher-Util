import hashlib
import os
import xlsxwriter
import datetime
import sys
import argparse

verbose_logging = False
log = None

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

def generate_spreadsheet(workbook, worksheet, hash_algorithms):
    headers = ["File Name", "File Path"]
    if len(hash_algorithms) == 1:
        headers.extend(["File Hash", "Size of File", "Date Created", "Date Modified"])
    else:
        headers.extend([f"File Hash ({algorithm.upper()})" for algorithm in hash_algorithms])

    bold = workbook.add_format({'bold': True})
    worksheet.write_row(0, 0, headers, bold)

def compare_directories(worksheet, hash_algorithms, workbook):
    headers = ["Matching"]
    headers.extend([f"File Hash ({algorithm.upper()})" for algorithm in hash_algorithms])
    bold = workbook.add_format({'bold': True})
    worksheet.write_row(0, 0, headers, bold)

def generate_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes):
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


def main():
    parser = argparse.ArgumentParser(description="Hasher Utility Script")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-c", "--compare", action="store_true", help="Compare hashes of two directories (uses all algorithms)")
    parser.add_argument("-d1", "--dir1", help="Path of the first directory to compare")
    parser.add_argument("-d2", "--dir2", help="Path of the second directory to compare")
    parser.add_argument("-a", "--algorithm", help="Hash algorithm to use (md5, sha1, sha256, sha512)")
    parser.add_argument("-dir", "--directory", help="Path of the directory for single-folder hash generation")
    parser.add_argument("-g", "--generate", action="store_true", help="If a report and spreadsheet should be made")
    args = parser.parse_args()

    print("Bulk Hasher v1.0.0")
    print("Made by: Aiden Fliss")
    print("Command line args:")
    print("-v --verbose Enable verbose logging")
    print("-c --compare Compare hashes of two directories (uses all algorithms)")
    print("-d1 <path> --dir1 Path of the first directory to compare")
    print("-d2 <path> --dir2 Path of the second directory to compare")
    print("-a --algorithm <alg.> Hash algorithm to use (md5, sha1, sha256, sha512)")
    print("-dir <path> --directory Path of the directory for single-folder hash generation")
    print("-g --generate If a report and spreadsheet should be made\n")

    global verbose_logging
    global log

    log = CustomLogger('output.log')

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
                try:
                    hashes = get_all_hashes(file_path)
                except Exception as e:
                    log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                    hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}  # Provide default algorithms
                hash_info_list_dir1.append((file, file_path, hashes))

        for root, _, files in os.walk(dir2):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    hashes = get_all_hashes(file_path)
                except Exception as e:
                    log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                    hashes = {algorithm: "HASHING_ERROR" for algorithm in ['md5', 'sha1', 'sha256', 'sha512']}  # Provide default algorithms
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
        hash_algorithms = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']
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

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if all_hashes:
                        hashes = get_all_hashes(file_path)
                    else:
                        hash_generator = get_hash(file_path, hash_option)
                        file_hash = next(hash_generator)
                        hashes = {hash_option: file_hash}
                        if verbose_logging:
                            log.log(f"{file_path} - {hash_generator.hexdigest()}", context="INFO", level="INFO")
                except Exception as e:
                    log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                    failed_hashes += 1
                    hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}

                hashed_files.append((file, file_path))
                successful_hashes += 1

                log.log(f"{file_path}: {' '.join(hashes.values()) if all_hashes else file_hash}")

                if args.generate:
                    hash_info_dict[file] = (file_path, hashes)

                    row += 1
                    worksheet.write(row, 0, file)
                    worksheet.write(row, 1, file_path)

                    if len(hash_algorithms) == 1:
                        worksheet.write(row, 2, hashes[hash_option])
                        worksheet.write(row, 3, os.path.getsize(file_path))
                        worksheet.write(row, 4, datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m/%d/%Y'))
                        worksheet.write(row, 5, datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m/%d/%Y'))
                    else:
                        col = 2
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
            generate_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes)

            log.log("Hash report generated.", context="REPORT")

    if not args.verbose and not args.compare and not args.generate:
        generate_report = False
        
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
                        print("Available hash algorithms:")
                        print("1. md5\n2. sha1\n3. sha224\n4. sha256\n5. sha384\n6. sha512")
                        hash_option = input("Choose a hash algorithm: ").lower()
                        if hash_option not in ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']:
                            log.log("Invalid hash algorithm.", context="ERROR", level="ERROR")
                            continue
                    else:
                        hash_option = 'all'
                    break
                else:
                    hash_option = 'all'
                    break

            hash_algorithms = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512', 'blake2s'] if hash_option == 'all' else [hash_option]
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

                for root, _, files in os.walk(compare_dir_1):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            hashes = get_all_hashes(file_path)
                        except Exception as e:
                            log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                            hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}
                        hash_info_list_dir1.append((file, file_path, hashes))

                for root, _, files in os.walk(compare_dir_2):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            hashes = get_all_hashes(file_path)
                        except Exception as e:
                            log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                            hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}
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

            else:
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if all_hashes:
                                hashes = get_all_hashes(file_path)
                            else:
                                hash_generator = get_hash(file_path, hash_option)
                                file_hash = next(hash_generator)
                                hashes = {hash_option: file_hash}
                                if verbose_logging:
                                    log.log(f"{file_path} - {hash_generator.hexdigest()}", context="INFO", level="INFO")
                        except Exception as e:
                            log.log(f"Error hashing {file_path}: {e}", context="ERROR", level="ERROR")
                            failed_hashes += 1
                            hashes = {algorithm: "HASHING_ERROR" for algorithm in hash_algorithms}

                        hashed_files.append((file, file_path))
                        successful_hashes += 1

                        log.log(f"{file_path}: {' '.join(hashes.values()) if all_hashes else file_hash}")

                        hash_info_dict[file] = (file_path, hashes)

                        if generate_report:
                            row += 1
                            worksheet.write(row, 0, file)
                            worksheet.write(row, 1, file_path)

                            if len(hash_algorithms) == 1:
                                worksheet.write(row, 2, hashes[hash_option])
                                worksheet.write(row, 3, os.path.getsize(file_path))
                                worksheet.write(row, 4, datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m/%d/%Y'))
                                worksheet.write(row, 5, datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%m/%d/%Y'))
                            else:
                                col = 2
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
                    generate_report(directory, successful_hashes, failed_hashes, hashed_files, start_time, end_time, all_hashes, hash_option, list_of_hashes)

                    log.log("Hash report generated.", context="REPORT")

                log.log("Finished comparing directories!", context="REPORT")

            if confirm_action("Do you want to quit?"):
                sys.exit(0)

if __name__ == "__main__":
    main()
