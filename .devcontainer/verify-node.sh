#!/bin/bash
node_paths=("/usr/local/bin/node" "/usr/bin/node")
required_version="18.18.0"

echo "Checking Node.js installation..."
echo "PATH=$PATH"

for node_path in "${node_paths[@]}"; do
    if [ -f "$node_path" ]; then
        echo "Node.js found at $node_path"
        ls -l "$node_path"
        
        if [ -x "$node_path" ]; then
            echo "Node.js is executable"
            current_version=$($node_path -v | cut -d 'v' -f 2)
            echo "Version: $current_version"
            
            if [ "$(printf '%s\n' "$required_version" "$current_version" | sort -V | head -n1)" = "$required_version" ]; then
                echo "Node.js version is adequate"
                exit 0
            else
                echo "Warning: Node.js version should be $required_version or higher"
            fi
        else 
            echo "Node.js is not executable, fixing permissions..."
            sudo chmod +x "$node_path"
            echo "New permissions:"
            ls -l "$node_path"
        fi
    fi
done

echo "Node.js not found in standard locations"
exit 1