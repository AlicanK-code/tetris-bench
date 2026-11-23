import math

def score(board, placement):
    # Calculate number of holes
    holes = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if not filled_rows:
            continue
        max_filled_row = max(filled_rows)
        for row in range(20):
            if not board[row][col]:
                if row < max_filled_row:
                    holes += 1
    
    # Calculate tallest column height
    tallest = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if filled_rows:
            current_max = max(filled_rows)
            if current_max > tallest:
                tallest = current_max
    
    # Calculate surface unevenness (standard deviation of column heights)
    column_heights = []
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if filled_rows:
            current_max = max(filled_rows)
            column_heights.append(current_max)
        else:
            column_heights.append(0)
    if not column_heights:
        std_dev = 0
    else:
        avg = sum(column_heights) / len(column_heights)
        variance = sum((h - avg) ** 2 for h in column_heights) / len(column_heights)
        std_dev = math.sqrt(variance)
    
    lines_cleared = placement["lines_cleared"]
    # Weighted score combining multiple metrics
    score_val = lines_cleared * 1000 - holes * 10 - tallest * 5 - std_dev * 10
    return float(score_val)
