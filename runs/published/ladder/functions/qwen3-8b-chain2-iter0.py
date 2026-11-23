def score(board, placement):
    # Calculate number of holes
    holes = 0
    for c in range(10):
        max_filled = -1
        for r in range(20):
            if board[r][c]:
                max_filled = r
        for r in range(20):
            if not board[r][c] and max_filled > r:
                holes += 1
    
    # Calculate tallest column and sum of column heights
    tallest = 0
    sum_heights = 0
    for c in range(10):
        max_filled = -1
        for r in range(20):
            if board[r][c]:
                max_filled = r
        column_height = max_filled if max_filled != -1 else 0
        sum_heights += column_height
        if column_height > tallest:
            tallest = column_height
    
    # Calculate filled cells
    filled_cells = sum(sum(row) for row in board)
    
    # Compute the score
    lines = placement["lines_cleared"]
    return lines * 1000 - holes * 10 - tallest + sum_heights * 0.1
