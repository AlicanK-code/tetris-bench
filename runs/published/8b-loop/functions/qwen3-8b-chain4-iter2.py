def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    holes = 0
    columns_heights = []
    for col in range(10):
        filled = False
        empty_count = 0
        current_max = 0
        for row in range(20):
            if board[row][col]:
                filled = True
                current_max = row
            else:
                empty_count += 1
        if filled:
            holes += empty_count
        columns_heights.append(current_max)
    max_h = max(columns_heights)
    average = sum(columns_heights) / len(columns_heights)
    surface = sum(abs(h - average) for h in columns_heights)
    score_val = lines_cleared * 1000 - holes * 100 - max_h * 20 - surface * 50
    return score_val
