#!/bin/bash

# Pre-commit hook to run isort on Python files
# This hook will automatically sort imports before committing

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running pre-commit hook: isort${NC}"

# Get list of Python files that are staged for commit
PYTHON_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')

if [ -z "$PYTHON_FILES" ]; then
    echo -e "${GREEN}No Python files to check.${NC}"
    exit 0
fi

echo -e "${YELLOW}Checking Python files for import sorting...${NC}"

# Check if isort is available
if ! command -v isort &> /dev/null; then
    echo -e "${RED}Error: isort is not installed or not in PATH${NC}"
    echo -e "${YELLOW}Please install isort: pip install isort${NC}"
    exit 1
fi

# Flag to track if any files were modified
FILES_MODIFIED=0

# Run isort on each Python file
for file in $PYTHON_FILES; do
    if [ -f "$file" ]; then
        echo "Checking $file..."
        
        # Run isort in check mode first to see if changes are needed
        if ! isort --check-only --quiet "$file"; then
            echo -e "${YELLOW}Fixing import order in $file${NC}"
            
            # Run isort to fix the file
            isort "$file"
            
            # Add the fixed file back to staging
            git add "$file"
            
            FILES_MODIFIED=1
        fi
    fi
done

if [ $FILES_MODIFIED -eq 1 ]; then
    echo -e "${GREEN}Import sorting complete. Modified files have been re-staged.${NC}"
    echo -e "${YELLOW}Please review the changes and commit again.${NC}"
    exit 1  # Exit with error to prevent commit, allowing user to review changes
else
    echo -e "${GREEN}All Python files have properly sorted imports.${NC}"
    exit 0
fi
