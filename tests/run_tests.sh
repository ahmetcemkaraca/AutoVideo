#!/bin/bash
echo "Running Bitrate Command Test..."
python tests/test_bitrate_cmd.py
if [ $? -ne 0 ]; then
    echo "Bitrate Test Failed!"
    exit 1
fi
echo "Bitrate Test Passed."

echo "Running Monitor Mock Test..."
python tests/test_monitor_mock.py
if [ $? -ne 0 ]; then
    echo "Monitor Test Failed!"
    exit 1
fi
echo "Monitor Test Passed."

echo "All verification tests passed!"
exit 0
