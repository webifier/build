from webifier.build import Builder
from webifier.build.io_utils import mix_folders
from .__version__ import __version__
import argparse
import os

BASE_INDEX_FILE = 'index.yml'
DEFAULT_OUTPUT_DIR = 'webified'
TARGET_INDEX_FILE = 'index.yml'


def main():
    parser = argparse.ArgumentParser(
        description=f'''
        Webify ({__version__}) current working directory starting from `index` and spit out the results in 
        `output` directory.
        '''
    )
    parser.add_argument('--remove-source', dest='remove_source',
                        action='store_true', default=False, help='Remove source notebook files')
    parser.add_argument('--baseurl', dest='base_url', default="",
                        help='Baseurl of deploying site')
    parser.add_argument('--repo_full_name',
                        dest='repo_full_name', help='user/repo_name')
    parser.add_argument('--index',
                        dest='index', help='initial page (default: index.yml)', default=BASE_INDEX_FILE)
    parser.add_argument('--output',
                        dest='output', help='build target directory (default: "webified")', default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(f'baseurl: {args.base_url}, repo_full_name: {args.repo_full_name}')

    mix_folders(root_src_dir='.', root_target_dir=args.output)  # todo: get file map
    mix_folders(root_src_dir=os.path.join(os.path.join(*os.path.split(__file__)[:-1], 'jekyll')),
                root_target_dir=args.output)
    builder = Builder(base_url=args.base_url, repo_full_name=args.repo_full_name, output_dir=args.output)
    builder.build_index(index_file=args.index, target_data_file=TARGET_INDEX_FILE, init_index=True)
    builder.save_search_list()
