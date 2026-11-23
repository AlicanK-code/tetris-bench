def score(board, placement):
    lines_cleared = placement['lines_cleared']
    
    holes = 0
    for j in range(10):
        has_filled_above = False
        for i in range(20):
            if board[i][j]:
                has_filled_above = True
            else:
                if has_filled_above:
                    holes += 1
    
    max_height = 0
    for j in range(10):
        height = 0
        for i in range(19, -1, -1):
            if board[i][j]:
                height += 1
            else:
                break
        if height > max_height:
            max_height = height
    
    col_heights = []
    for j in range(10):
        height = 0
        for i in range(19, -1, -1):
            if board[i][j]:
                height += 1
            else:
                break
        col_heights.append(height)
    
    surface_unevenness = 0
    for i in range(9):
        surface_unevenness += abs(col_heights[i] - col_heights[i+1])
    
    return (lines_cleared * 100) - (holes * 20) - (max_height * 5) - surface_unevenness - (placement['column'] * 0.1)
