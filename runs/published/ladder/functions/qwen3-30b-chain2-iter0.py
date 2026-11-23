def score(board, placement):
    holes = 0
    for col in range(10):
        found_filled = False
        for row in range(20):
            if board[row][col]:
                found_filled = True
            elif found_filled:
                holes += 1
    
    max_row = [-1] * 10
    for col in range(10):
        for row in range(19, -1, -1):
            if board[row][col]:
                max_row[col] = row
                break
    max_height = max(max_row)
    
    roughness = 0
    for col in range(9):
        roughness += abs(max_row[col] - max_row[col+1])
    
    return (placement['lines_cleared'] * 1000) - (holes * 10) - (max_height * 5) - (roughness * 2)
