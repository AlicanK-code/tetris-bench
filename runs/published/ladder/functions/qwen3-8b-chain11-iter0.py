def score(board, placement):
    # Compute holes
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
    # Compute max_height (max number of filled cells in any column)
    max_height = 0
    for col in range(10):
        cnt = 0
        for row in board:
            if row[col]:
                cnt += 1
        max_height = max(max_height, cnt)
    # Compute empty_rows
    empty_rows = 0
    for row in board:
        if all(not cell for cell in row):
            empty_rows += 1
    # Compute variance of column heights
    columns_heights = []
    for col in range(10):
        cnt = 0
        for row in board:
            if row[col]:
                cnt += 1
        columns_heights.append(cnt)
    average = sum(columns_heights) / len(columns_heights)
    variance = sum((h - average)**2 for h in columns_heights) / len(columns_heights)
    # lines_cleared is from placement
    lines = placement["lines_cleared"]
    # Combine all terms
    return lines * 1000 - holes * 10 - max_height * 5 - empty_rows * 2 - variance * 3
