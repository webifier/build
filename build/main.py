from src import Builder
import argparse

BASE_INDEX_FILE = 'index'
TARGET_INDEX_FILE = 'index'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build index.')
    parser.add_argument('--remove-source', dest='remove_source',
                        action='store_true', default=False, help='Remove source notebook files')
    parser.add_argument('--baseurl', dest='base_url', default="",
                        help='Baseurl of deploying site')
    parser.add_argument('--repo_full_name',
                        dest='repo_full_name', help='user/repo_name')
    parser.add_argument('--index',
                        dest='index', help='index.yml file path', default=BASE_INDEX_FILE)
    args = parser.parse_args()

    print(f'baseurl: {args.base_url}, repo_full_name: {args.repo_full_name}')

    builder = Builder(base_url=args.base_url, repo_full_name=args.repo_full_name )
    builder.build_index(index_file=args.index, target_data_file=TARGET_INDEX_FILE)
