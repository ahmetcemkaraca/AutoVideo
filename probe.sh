for f in /root/Desktop/AutoVideo/*.mp4; do
    echo "--- File: $f ---"
    echo -n "Duration: "
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$f"
    echo -n "Audio: "
    ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$f"
done
