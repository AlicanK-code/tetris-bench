def score(board, placement):
    # Calculate holes
    holes = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if not filled_rows:
            continue
        lowest_filled_row = max(filled_rows)
        for row in range(lowest_filled_row):
            if not board[row][col]:
                holes += 1
    # Calculate tallest column height
    tallest = 0
    for col in range(10):
        filled_rows = []
        for row in range(20):
            if board[row][col]:
                filled_rows.append(row)
        if filled_rows:
            current_height = max(filled_rows)
            if current_height > tallest:
                tallest = current_height
    # Calculate score
    lines = placement["lines_cleared"]
    return lines * 100 - holes * 10 - tallest * 5
