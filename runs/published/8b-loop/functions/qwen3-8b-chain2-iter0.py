def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        filled = False
        for r in reversed(range(20)):
            if board[r][c]:
                filled = True
            else:
                if filled:
                    holes += 1
    
    # Calculate max_height
    max_height = 0
    for c in range(10):
        current_max = 0
        for r in range(20):
            if board[r][c]:
                current_max = r
        max_height = max(max_height, current_max)
    
    # Calculate empty_bottom_rows
    empty_bottom_rows = 0
    for r in reversed(range(20)):
        if all(not cell for cell in board[r]):
            empty_bottom_rows += 1
        else:
            break
    
    return lines * 1000 - holes - max_height - empty_bottom_rows
