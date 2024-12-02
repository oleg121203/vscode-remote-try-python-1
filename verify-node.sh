
#!/bin/bash
node_path="/usr/local/bin/node"
if [ -x "$node_path" ]; then
    echo "Node.js найден и исполняемый"
    $node_path -v
else
    echo "Node.js не найден или не исполняемый"
fi