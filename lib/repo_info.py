from datetime import datetime
import subprocess


def get_repo_info(folder):
    output = subprocess.check_output(
        ['git', 'log', '-n', '1', '--pretty=format:%H %cd', '--date=iso', '--', folder],
        encoding='UTF-8',
        cwd=folder,
    )
    output = output.strip("\n")

    commit_hash, commit_timestamp = output.split(' ', maxsplit=1)

    commit_timestamp = datetime.strptime(commit_timestamp.strip(), "%Y-%m-%d %H:%M:%S %z")

    return commit_hash, commit_timestamp

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('folder', help='Please supply a folder')

    args = parser.parse_args()  # script will exit if arguments not present

    a,b = get_repo_info(args.folder)
    print(a)
    print(b)
