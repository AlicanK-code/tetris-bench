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
    
    # Calculate top_empty
    top_empty = 0
    for col in range(10):
        cnt = 0
        for row in range(20):
            if not board[row][col]:
                cnt += 1
            else:
                break
        if cnt > top_empty:
            top_empty = cnt
    
    # Calculate column heights for evenness
    column_heights = []
    for col in range(10):
        cnt = 0
        for row in range(20):
            if board[row][col]:
                cnt += 1
        column_heights.append(cnt)
    
    # Standard deviation of column heights
    mean = sum(column_heights) / 10
    variance = sum((h - mean)**2 for h in column_heights) / 10
    std_dev = variance**0.5
    
    # Combine into score
    score_val = lines * 100 - holes - max_col_height - top_empty - std_dev
    return score_val
