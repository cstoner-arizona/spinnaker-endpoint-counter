import os
import git
import javalang
import re
import json

def clone_repo(repo_url):
    """
    Clones the spinnaker repository if not already cloned.
    If already cloned, pulls changes instead.

    :param repo_url: URL of the spinnaker repository.
    :return: git.Repo object
    """
    clone_dir = './spinnaker'
    repo = None
    try:
        if os.path.exists(clone_dir):
            print('Repo already cloned, skipping clone step...')
            repo = git.Repo(clone_dir)
            print('Pulling latest changes...')
            repo.git.pull()
        else:
            print(f"Cloning {repo_url} into {clone_dir}...")
            repo = git.Repo.clone_from(repo_url, clone_dir)
            print(f"Successfully cloned {repo_url} to {clone_dir}")
    except Exception as e:
        print(f"Failed to clone {repo_url} to {clone_dir}: {e}")
    return repo


def get_microservice_dirs(repo: git.Repo) -> list:
    """
    Find directories likely to be microservices.
    Indicators being:
    - pom.xml (Maven) or build.gradle (Gradle)
    - Contains src/main/java structure
    - Top-level or second-level directories

    :param repo: git.Repo object
    :return: List of paths likely to be microservices.
    """
    repo_root = repo.working_dir
    microservices = []

    # Check top-level and one level deep
    for root, dirs, files in os.walk(repo_root):
        # Skip .git
        if '.git' in dirs:
            dirs.remove('.git')

        # Only check up to 2 levels deep
        depth = root[len(repo_root):].count(os.sep)
        if depth > 1:
            dirs[:] = []  # Don't go deeper
            continue

        # Check if this directory looks like a microservice
        has_pom = 'pom.xml' in files
        has_gradle = 'build.gradle' in files or 'build.gradle.kts' in files

        if has_pom or has_gradle:
            rel_path = os.path.relpath(root, repo_root)
            if rel_path == '.':
                continue
            microservices.append(rel_path)

    return microservices

def crawl_microservice(repo, microservice_path, search_patterns=None) -> dict:
    """
    Crawl a single microservice directory for controllers (excluding tests)

    :param repo: git.Repo object
    :param microservice_path: Relative path to microservice (e.g. 'igor', 'fiat')
    :param search_patterns: Optional patterns to identify controllers
    :return: Dictionary with microservice analysis results that will be used by deeper analysis methods
    """
    if search_patterns is None:
        search_patterns = {
            'directory_names': ['controller', 'controllers', 'rest'],
            'file_suffixes': ['Controller.java', 'Resource.java', 'Endpoint.java'],
            'annotations': ['@RestController', '@Controller']
        }
    # Common build/cache dirs
    skipped_dirs = ['target', 'build', 'node_modules', '.idea', '.gradle', 'test', 'tests', 'testing']
    file_extensions = ['.java', '.groovy', '.kt', '.scala']

    repo_root = repo.working_dir
    microservice_full_path = os.path.join(repo_root, microservice_path)
    print(f"\nCrawling {microservice_path}...")
    print(f"   Full path: {microservice_full_path}")

    controller_files = []

    # Walk through microservice directory
    for root, dirs, files in os.walk(microservice_full_path):
        # Skip common build/cache dirs
        dirs[:] = [d for d in dirs if d not in skipped_dirs]

        for file in files:
            # If ends in undefined file extension, skip
            if not any(file.endswith(ext) for ext in file_extensions):
                continue

            filepath = os.path.join(root, file)
            is_controller = False

            # Check file name pattern (w/o extension)
            # file_base = os.path.splitext(file)[0]
            # for suffix in search_patterns['file_suffixes']:
            #     if file_base.endswith(suffix):
            #         is_controller = True
            #         break

            # Check directory name pattern
            # if not is_controller:
            #     path_lower = root.lower()
            #     for pattern in search_patterns['directory_names']:
            #         if pattern in path_lower:
            #             is_controller = True
            #             break

            # Check file content has controller annotations
            if not is_controller:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(5000)
                        for annotation in search_patterns['annotations']:
                            if annotation in content:
                                is_controller = True
                                break
                except Exception as e:
                    print(f"Failed to read {filepath}: {e}")
                    print(f"Skipping {filepath}...")
                    continue

            if is_controller:
                rel_path = os.path.relpath(filepath, repo_root)
                controller_files.append(rel_path)

    print(f"Found {len(controller_files)} controller files")

    return_dict = {
        'microservice': microservice_path,
        'controller_files': controller_files,
        'full_path': microservice_full_path
    }
    return return_dict

def has_valid_uri_javalang(annotation):
    """
    Check if annotation has a non-empty URI/path parm.
    :param annotation: javalang annotation node
    :return: True if has valid non-empty URI, False otherwise
    """
    if not annotation.element:
        return False

    # Handle single value annotation like @GetMapping("/users")
    if isinstance(annotation.element, javalang.tree.Literal):
        value = annotation.element.value
        return value and value.strip() not in ['""', "''"]

    # Handle named params like @GetMapping(value = "/users") or path = "/users"
    # Also handle arrays like @GetMapping({"/users", "/all-users"})
    if isinstance(annotation.element, list):
        for elem in annotation.element:
            if isinstance(elem, javalang.tree.ElementValuePair):
                if elem.name in ['value', 'path']:
                    # Check if literal
                    if isinstance(elem.value, javalang.tree.Literal):
                        value = elem.value.value
                        return value and value.strip() not in ['""', "''"]
                    # Check if array of literals
                    elif isinstance(elem.value, list):
                        # If any value in the array is non-empty, valid uri
                        for item in elem.value:
                            if isinstance(item, javalang.tree.Literal):
                                value = item.value
                                if value and value.strip() not in ['""', "''", '{}']:
                                    return True
    return False

def count_endpoints_in_file(file_path) -> list:
    """
    Count valid endpoints in a single controller file.
    Handles Java with javalang and Groovy/Kotlin (.groovy, .kt) with regex

    :param file_path: Full path to the controller file
    :return: List of endpoint dictionaries with method name and annotation type
    """
    endpoints = []
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Use javalang for java files
        if file_ext == '.java':
            endpoints = count_endpoints_java(file_path, content)
        else:
            # Use regex for Groovy, Kotlin, Scala, or other JVM lang
            endpoints = count_endpoints_regex(file_path, content)
    except Exception as e:
        print(f"Failed to count endpoints: {e}")

    return endpoints

def count_endpoints_java(file_path, content):
    """
    Count endpoints in Java files using javalang AST parsing

    :param file_path: Full path to file
    :param content: File content as string
    :return: List of endpoint dictionaries
    """
    endpoints = []
    try:
        tree = javalang.parse.parse(content)

        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            if node.annotations:
                for annotation in node.annotations:
                    if annotation.name in ['GetMapping', 'PostMapping',
                                           'PutMapping', 'DeleteMapping',
                                           'PatchMapping','RequestMapping']:
                        if has_valid_uri_javalang(annotation):
                            endpoints.append({
                                'method': node.name,
                                'annotation': annotation.name
                            })
    except javalang.parser.JavaSyntaxError as e:
        print(f"Syntax error parsing {file_path}: {e}")
        print(f"Falling back to regex parsing for {file_path}...")
        endpoints = count_endpoints_regex(file_path, content)
    except Exception as e:
        print(f"Failed to count endpoints: {e}")

    return endpoints


def count_endpoints_regex(file_path, content):
    """
    Count endpoints using regex pattern matching.
    Meant for Groovy, Kotlin, Scala, or fallback for failed Java parses

    :param file_path: full path to file
    :param content: file content as string
    :return: list of endpoint dictionaries
    """
    endpoints = []

    mapping_annotations = [
        'GetMapping', 'PostMapping', 'PutMapping',
        'DeleteMapping', 'PatchMapping', 'RequestMapping'
    ]

    # Attempts to match patterns like:
    # @GetMapping("/users")
    # @PostMapping(value = "/users")
    # @RequestMapping(path = "/api/users")
    # @GetMapping(["/users", "/all-users"])
    # @GetMapping(value = ["/users", "/all-users"])
    for annotation_name in mapping_annotations:
        # Pattern explanation:
        # @AnnotationName - the annotation
        # \s* - optional whitespace
        # \( - opening parenthesis
        # (?:value\s*=\s*|path\s*=\s*)? - optional "value =" or "path ="
        # (["'][^"']+["']|\[.*?\]) - capture either a string or an array
        # [^)]* - any other parameters
        # \) - closing parenthesis

        # Simple string value @GetMapping("/path")
        pattern1 = rf'@{annotation_name}\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?(["\']).+?\1'

        # Array value @GetMapping(["/path1", "/path2"])
        pattern2 = rf'@{annotation_name}\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?\[.+?\]'

        # Find all matches for both patterns
        matches1 = re.finditer(pattern1, content, re.DOTALL)
        matches2 = re.finditer(pattern2, content, re.DOTALL)

        # Count matches and attempt method name extraction
        for match in matches1:
            method_name = extract_method_name_near_annotation(content, match.start())
            endpoints.append({
                'method': method_name or 'unknown',
                'annotation': annotation_name
            })

        for match in matches2:
            method_name = extract_method_name_near_annotation(content, match.start())
            endpoints.append({
                'method': method_name or 'unknown',
                'annotation': annotation_name
            })

    return endpoints

def extract_method_name_near_annotation(content, annotation_pos):
    """
    Attempt to extract the method name that follows an annotation.

    :param content: Full file content
    :param annotation_pos: Position where annotation starts
    :return: Method name or None if not found
    """
    snippet = content[annotation_pos:annotation_pos + 500]
    method_pattern = r'(?:public|private|protected)?\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?(?:\[\])?\s+)?(\w+)\s*\('

    match = re.search(method_pattern, snippet)
    if match:
        return match.group(1)

    return None

def analyze_microservice_endpoints(repo, microservice_path):
    """
    Crawl a microservice and count all valid endpoints

    :param repo: git.Repo object
    :param microservice_path: Relative path to microservice
    :return: Dictionary with detailed analysis
    """
    crawl_results = crawl_microservice(repo, microservice_path)

    if crawl_results is None:
        return None

    repo_root = repo.working_dir
    all_endpoints = []

    print(f"Analyzing endpoints in {microservice_path}...")

    for controller_rel_path in crawl_results['controller_files']:
        controller_full_path = os.path.join(repo_root, controller_rel_path)
        file_endpoints = count_endpoints_in_file(controller_full_path)

        # Add file info to endpoint
        for endpoint in file_endpoints:
            endpoint['file'] = controller_rel_path
            all_endpoints.append(endpoint)

        if file_endpoints:
            print(f"{os.path.basename(controller_rel_path)}: {len(file_endpoints)} endpoints")

    return {
        'microservice': microservice_path,
        'controller_files': crawl_results['controller_files'],
        'total_controllers': len(crawl_results['controller_files']),
        'total_endpoints': len(all_endpoints),
        'endpoints': all_endpoints
    }


def main():
    repo = clone_repo('https://github.com/spinnaker/spinnaker.git')
    repo_dirs = get_microservice_dirs(repo)

    all_results = []

    print("\n" + "=" * 60)
    print("ANALYZING MICROSERVICES")
    print("=" * 60)

    for microservice_path in repo_dirs:
        results = analyze_microservice_endpoints(repo, microservice_path)
        if results:
            all_results.append(results)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_controllers = sum(r['total_controllers'] for r in all_results)
    total_endpoints = sum(r['total_endpoints'] for r in all_results)

    print(f"Total microservices analyzed: {len(all_results)}")
    print(f"Total controllers found: {total_controllers}")
    print(f"Total valid endpoints: {total_endpoints}")

    print("\nBreakdown by microservice:")
    for result in all_results:
        print(
            f"  {result['microservice']:30s} - {result['total_endpoints']:3d} endpoints from {result['total_controllers']:2d} controllers")

    with open('spinnaker_analysis.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print("\nDetailed results saved to 'spinnaker_analysis.json'")
    return all_results

if __name__ == '__main__':
    main()