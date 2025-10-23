# Spinnaker Microservices Endpoint Analysis

A Python tool to analyze and count REST API endpoints in Spinnaker microservices by parsing controller files across multiple JVM languages (Java, Groovy, Kotlin, Scala).

## Overview

This tool automatically:
1. Clones the Spinnaker repository
2. Identifies microservice directories
3. Finds Spring controller files (@RestController, @Controller)
4. Counts valid REST endpoints with non-empty URIs
5. Generates a detailed JSON report

## Features

- **Multi-language Support**: Handles Java (via AST parsing), Groovy, Kotlin, and Scala (via regex)
- **Smart Filtering**: Excludes test files and build artifacts
- **Endpoint Validation**: Only counts endpoints with valid, non-empty URI mappings
- **Detailed Reporting**: Provides breakdown by microservice with JSON export

## Requirements

```bash
pip install gitpython javalang
```

### Dependencies
- `gitpython` (>= 3.1.0) - Git repository management
- `javalang` (>= 0.13.0) - Java source code parsing

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd <your-repo-directory>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install gitpython javalang
```

## Usage

Run the analysis:
```bash
python main.py
```

The script will:
1. Clone/update the Spinnaker repository to `./spinnaker/`
2. Scan for microservices (directories with `pom.xml` or `build.gradle`)
3. Identify controller files in each microservice
4. Count valid REST endpoints
5. Output results to console and `spinnaker_analysis.json`

## How It Works

### 1. Microservice Detection
Identifies directories as microservices if they contain:
- `pom.xml` (Maven project)
- `build.gradle` or `build.gradle.kts` (Gradle project)

### 2. Controller Detection
Finds files containing Spring controller annotations:
- `@RestController`
- `@Controller`

Excludes:
- Test directories (`src/test/`, `tests/`, etc.)
- Test files (`*Test.java`, `*IT.java`, etc.)
- Build artifacts (`target/`, `build/`, etc.)

### 3. Endpoint Counting
Counts methods with Spring mapping annotations that have valid URIs:

**Supported Annotations:**
- `@GetMapping`
- `@PostMapping`
- `@PutMapping`
- `@DeleteMapping`
- `@PatchMapping`
- `@RequestMapping`

**Valid Endpoint Examples:**
```java
@GetMapping("/users")                          // ✓ Valid
@PostMapping(value = "/users")                 // ✓ Valid
@RequestMapping(path = "/api/orders")          // ✓ Valid
@GetMapping({"/users", "/all-users"})          // ✓ Valid (counts as 1 endpoint)
```

**Filtered Out:**
```java
@GetMapping()                                  // ✗ No URI
@GetMapping("")                                // ✗ Empty string
@PostMapping(value = "")                       // ✗ Empty value
```

### 4. Parsing Strategy

- **Java files (`.java`)**: Uses `javalang` for accurate AST parsing
- **Other JVM languages (`.groovy`, `.kt`, `.scala`)**: Uses regex-based pattern matching
- **Fallback**: If Java parsing fails, falls back to regex

## Output

### Console Output
```
ANALYZING MICROSERVICES
============================================================

Crawling clouddriver...
Found 15 controller files

Analyzing endpoints in clouddriver...
ApplicationsController.java: 12 endpoints
AccountsController.java: 8 endpoints
...

============================================================
SUMMARY
============================================================
Total microservices analyzed: 10
Total controllers found: 78
Total valid endpoints: 456

Breakdown by microservice:
  clouddriver                    -  89 endpoints from 15 controllers
  deck                           -   0 endpoints from  0 controllers
  echo                           -  23 endpoints from  4 controllers
  fiat                           -  45 endpoints from  7 controllers
  ...
```

### JSON Output (`spinnaker_analysis.json`)
```json
[
  {
    "microservice": "clouddriver",
    "controller_files": [
      "clouddriver/clouddriver-web/src/main/groovy/com/netflix/spinnaker/clouddriver/controllers/ApplicationsController.groovy",
      ...
    ],
    "total_controllers": 15,
    "total_endpoints": 89,
    "endpoints": [
      {
        "method": "getApplications",
        "annotation": "RequestMapping",
        "file": "clouddriver/clouddriver-web/src/main/groovy/..."
      },
      ...
    ]
  },
  ...
]
```

## Configuration

### Custom Repository
Modify the repository URL in `main()`:
```python
repo = clone_repo('https://github.com/your-org/your-repo.git')
```

### Custom Search Patterns
Modify `crawl_microservice()` to customize controller detection:
```python
search_patterns = {
    'directory_names': ['controller', 'controllers', 'api'],
    'file_suffixes': ['Controller.java', 'Resource.java'],
    'annotations': ['@RestController', '@Controller']
}
```

### File Extensions
Add support for additional languages in `crawl_microservice()`:
```python
file_extensions = ['.java', '.groovy', '.kt', '.scala', '.clj']
```

## Project Structure

```
.
├── main.py                      # Main analysis script
├── spinnaker/                   # Cloned Spinnaker repository (auto-generated)
├── spinnaker_analysis.json      # Generated analysis results
├── README.md                    # This file
└── requirements.txt             # Python dependencies
```

## Function Reference

### `clone_repo(repo_url)`
Clones or updates the repository.
- **Parameters**: `repo_url` (str) - Git repository URL
- **Returns**: `git.Repo` object

### `get_microservice_dirs(repo)`
Identifies microservice directories.
- **Parameters**: `repo` (git.Repo) - Repository object
- **Returns**: List of relative paths to microservices

### `crawl_microservice(repo, microservice_path, search_patterns=None)`
Finds controller files in a microservice.
- **Parameters**: 
  - `repo` (git.Repo) - Repository object
  - `microservice_path` (str) - Relative path to microservice
  - `search_patterns` (dict, optional) - Custom search patterns
- **Returns**: Dictionary with controller file paths

### `count_endpoints_in_file(file_path)`
Counts endpoints in a single controller file.
- **Parameters**: `file_path` (str) - Full path to controller file
- **Returns**: List of endpoint dictionaries

### `analyze_microservice_endpoints(repo, microservice_path)`
Performs complete endpoint analysis for a microservice.
- **Parameters**: 
  - `repo` (git.Repo) - Repository object
  - `microservice_path` (str) - Relative path to microservice
- **Returns**: Dictionary with analysis results

## Limitations

- **Regex Accuracy**: Non-Java files use regex parsing, which may miss complex annotation patterns
- **Dynamic Endpoints**: Only counts statically-defined endpoints (no runtime-generated paths)
- **Annotation Detection**: Requires annotations to be in standard Spring format
- **Method Name Extraction**: In non-Java files, method names may be marked as "unknown" if pattern matching fails
- **IDE Warnings**: `javalang.tree.MethodDeclaration` may show IDE warnings due to dynamic module loading, but works correctly at runtime

## Research Context

This tool was developed to analyze REST API endpoints in microservice architectures for research purposes. It focuses on:
- **Functional endpoints**: Each method counts as one endpoint, regardless of multiple URI mappings
- **Production code only**: Excludes test files to focus on deployed endpoints
- **Static analysis**: Analyzes source code without requiring compilation or runtime execution

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'git'"
**Solution**: Install gitpython: `pip install gitpython`

### Issue: "ModuleNotFoundError: No module named 'javalang'"
**Solution**: Install javalang: `pip install javalang`

### Issue: IDE shows warnings for `javalang.tree.MethodDeclaration`
**Solution**: This is expected due to dynamic module loading in javalang. The code works correctly at runtime. You can add `# type: ignore` to suppress warnings.

### Issue: Repository clone is slow
**Solution**: The first clone downloads the entire Spinnaker repository. Subsequent runs will use `git pull` which is much faster. You can also manually clone with `--depth 1` for a shallow clone.

### Issue: Parsing errors in specific files
**Solution**: The tool automatically falls back to regex parsing when javalang fails. Check console output for fallback messages.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Areas for Improvement
- Add support for additional Spring annotations
- Improve regex patterns for non-Java languages
- Add support for Spring WebFlux reactive endpoints
- Add parallel processing for faster analysis
- Add support for custom annotation patterns

## Author

C. Stoner - University of Arizona - CloudHubs

## Acknowledgments

- Built for microservice endpoint analysis research
- Uses the Spinnaker open-source project as a case study
- Leverages `javalang` for Java AST parsing
- Uses `gitpython` for Git repository management