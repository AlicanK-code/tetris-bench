def score(board, placement):
    # Calculate number of holes
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
    # Calculate maximum column height
    max_h = 0
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
            else:
                break
        max_h = max(max_h, count)
    # Calculate column heights for unevenness metric
    column_counts = []
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
            else:
                break
        column_counts.append(count)
    # Compute sum of squared deviations from average height
    avg_h = sum(column_counts) / 10.0
    sum_of_squares_diff = sum((h - avg_h) ** 2 for h in column_counts)
    # Combine all metrics into a score
    lines = placement["lines_cleared"]
    return lines * 100 - holes * 150 - max_h * 100 - sum_of_squares_diff * 100
