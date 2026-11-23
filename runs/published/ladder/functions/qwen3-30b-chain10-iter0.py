def score(board, placement):
    l = placement["lines_cleared"]
    
    heights = []
    for col in range(10):
        h = 0
        for row in range(19, -1, -1):
            if board[row][col]:
                h += 1
            else:
                break
        heights.append(h)
    max_height = max(heights)
    
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(19, -1, -1):
            if board[row][col]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
    
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i+1])
    
    unique_term = (placement["column"] * 10 + placement["rotation"]) / 100.0
    
    return l * 1000 - max_height * 50 - holes * 5 - bumpiness + unique_term
