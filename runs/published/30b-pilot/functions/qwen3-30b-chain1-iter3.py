def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for col in range(10):
        filled = False
        for row in range(20):
            if board[row][col]:
                filled = True
            elif filled:
                holes += 1
                
    heights = []
    for col in range(10):
        top_filled = -1
        for row in range(20):
            if board[row][col]:
                top_filled = row
                break
        height = 20 - top_filled if top_filled != -1 else 0
        heights.append(height)
        
    max_height = max(heights)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i+1])
        
    unique_term = (placement["row"] * 10 + placement["column"]) * 10
    return lines * 1000 - holes * 50 - max_height * 50 - bumpiness * 15 + unique_term
