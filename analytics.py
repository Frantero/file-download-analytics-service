from collections import Counter
from typing import Sequence

def count_digits(text: str) -> dict[str, int]:
    stats = {str(i): 0 for i in range(10)}
    counts = Counter(text)
    for digit in stats:
        stats[digit] = counts.get(digit, 0)
    return stats


def calculate_files_statistics(files: Sequence) -> dict:
    total_stats = {str(i): 0 for i in range(10)}
    file_stats = []
    
    for file in files:
        f_counts = count_digits(file.content)
        for digit, count in f_counts.items():
            total_stats[digit] += count

        file_stats.append({
            "file_id": file.id,
            "filename": file.filename,
            "downloaded_at": file.downloaded_at,
            "stats": f_counts
        })

    return {
        "total_files_count": len(files),
        "total_stats": total_stats,
        "file_stats": file_stats
    }