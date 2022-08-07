RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

g++ -std=c++17 $1.cpp -lm -Wall -g -Wconversion -Wshadow -Wextra -D_GLIBCXX_DEBUG -DLSHT_DEBUG -fsanitize=address -o $1

if [ $? -ne 0 ]; then
    echo -e "${RED}Compilation Error.${NC}"
    exit 1
else
    echo -e "${GREEN}Compilation Finished.${NC}"
    exit 0
fi
