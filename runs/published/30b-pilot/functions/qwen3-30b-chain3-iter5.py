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
    
    base_score = lines * 1500 - holes * 7.5 - bumpiness * 2 - (max_height ** 2) * 0.2
    
    tiebreaker = placement['column'] * 0.1 + placement['rotation'] * 0.01
    
    return base_score + tiebreaker
