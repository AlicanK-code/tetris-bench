def score(board, placement):
    lines = placement['lines_cleared']
    
    holes = 0
    for j in range(10):
        has_filled = False
        for i in range(20):
            if board[i][j]:
                has_filled = True
            elif has_filled:
                holes += 1
                
    heights = []
    for j in range(10):
        h = 0
        for i in range(19, -1, -1):
            if board[i][j]:
                h += 1
            else:
                break
        heights.append(h)
    max_height = max(heights)
    
    bumpiness = 0
    for j in range(9):
        bumpiness += abs(heights[j] - heights[j+1])
    
    base_score = lines * 500 - holes * 800 - bumpiness * 200 - (max_height ** 2) * 15
    
    tiebreaker = placement['column'] * 0.01 + placement['rotation'] * 0.001
    
    return base_score + tiebreaker
