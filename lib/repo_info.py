from datetime import datetime
import subprocess


def get_repo_info(folder):
    output = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'],
        encoding='UTF-8',
        cwd=folder,
    )
    commit_hash = output.strip("\n")

    output = subprocess.check_output(
        ['git', 'show', '-s', '--format=%ci'],
        encoding='UTF-8',
        cwd=folder,
    )

    commit_timestamp = output.strip("\n")
    commit_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%d %H:%M:%S %z")

    return commit_hash, commit_timestamp

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('folder', help='Please supply a folder')

    args = parser.parse_args()  # script will exit if arguments not present

    a,b = get_repo_info(args.folder)
    print(a)
    print(b)
