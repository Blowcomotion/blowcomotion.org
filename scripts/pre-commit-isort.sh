#!/bin/bash

# Pre-commit hook to run isort on Python files and check for inline imports
# This hook will automatically sort imports before committing and warn about inline imports

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running pre-commit hook: isort and import validation${NC}"

# Get list of Python files that are staged for commit
PYTHON_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')

if [ -z "$PYTHON_FILES" ]; then
    echo -e "${GREEN}No Python files to check.${NC}"
    exit 0
fi

echo -e "${YELLOW}Checking Python files for import sorting and inline imports...${NC}"

# Check if isort is available
if ! command -v isort &> /dev/null; then
    echo -e "${RED}Error: isort is not installed or not in PATH${NC}"
    echo -e "${YELLOW}Please install isort: pip install isort${NC}"
    exit 1
fi

# Flag to track if any files were modified or have issues
FILES_MODIFIED=0
INLINE_IMPORTS_FOUND=0

# Run isort on each Python file
for file in $PYTHON_FILES; do
    if [ -f "$file" ]; then
        echo "Checking $file..."
        
        # Check for inline imports (imports not at the top level)
        INLINE_IMPORTS=$(grep -n '^\s\+\(import\|from .* import\)' "$file" || true)
        if [ -n "$INLINE_IMPORTS" ]; then
            echo -e "${YELLOW}Warning: Found inline imports in $file:${NC}"
            echo "$INLINE_IMPORTS"
            echo -e "${YELLOW}Consider moving these imports to the top of the file.${NC}"
            INLINE_IMPORTS_FOUND=1
        fi
        
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

if [ $INLINE_IMPORTS_FOUND -eq 1 ]; then
    echo -e "${YELLOW}Note: Some files have inline imports. While the commit will proceed,${NC}"
    echo -e "${YELLOW}consider moving imports to the top of the file for better code organization.${NC}"
fi

if [ $FILES_MODIFIED -eq 1 ]; then
    echo -e "${GREEN}Import sorting complete. Modified files have been re-staged.${NC}"
    echo -e "${YELLOW}Please review the changes. Proceeding with commit.${NC}"
    exit 0  # Exit successfully to allow commit to proceed
else
    echo -e "${GREEN}All Python files have properly sorted imports.${NC}"
    exit 0
fi
