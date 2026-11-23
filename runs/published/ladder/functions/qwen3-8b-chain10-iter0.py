def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate hole count
    hole_count = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                for r2 in range(r + 1, 20):
                    if board[r2][c]:
                        hole_count += 1
                        break
    
    # Calculate maximum column height
    max_height = 0
    for c in range(10):
        count = sum(1 for r in range(20) if board[r][c])
        if count > max_height:
            max_height = count
    
    # Calculate filled cells
    filled_cells = sum(1 for row in board for cell in row if cell)
    
    # Combine metrics with appropriate weights
    return lines_cleared * 1000 - hole_count * 1 - max_height * 1 - filled_cells * 0.1
