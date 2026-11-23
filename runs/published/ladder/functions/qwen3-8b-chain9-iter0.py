def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
    
    # Calculate max_col_height
    max_col_height = 0
    for col in range(10):
        cnt = 0
        for row in range(20):
            if board[row][col]:
                cnt += 1
        if cnt > max_col_height:
            max_col_height = cnt
    
    # Calculate max_empty_rows
    max_empty_rows = 0
    for col in range(10):
        empty_rows = 0
        for row in range(20):
            if not board[row][col]:
                empty_rows = row
                break
        if empty_rows > max_empty_rows:
            max_empty_rows = empty_rows
    
    # Combine into score
    return lines * 100 - holes - max_col_height - max_empty_rows
