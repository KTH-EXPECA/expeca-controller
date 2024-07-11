#!/bin/bash

# run authentication
file_path="openstack-openrc.sh"
# Check if file exists
if [[ -e "$file_path" ]]; then
    echo "File exists: $file_path"
else
    echo "File does not exist: $file_path"
    exit 1
fi
chmod +x openstack-openrc.sh 
./openstack-openrc.sh

# run check_authentication.py
python3 check_authentication.py

# run main.py
#python3 main.py
