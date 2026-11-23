def score(board, placement):
    lines = placement["lines_cleared"]
    
    holes = 0
    for col in range(10):
        found_filled = False
        for row in range(20):
            if board[row][col]:
                found_filled = True
            elif found_filled:
                holes += 1
    
    surface_heights = []
    for col in range(10):
        top = 20
        for row in range(20):
            if board[row][col]:
                top = row
                break
        surface_heights.append(top)
    
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(surface_heights[i] - surface_heights[i+1])
    
    return lines * 100 - holes * 10 - bumpiness * 5 + placement["rotation"] * 0.01
