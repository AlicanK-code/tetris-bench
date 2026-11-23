def score(board, placement):
    holes = 0
    for c in range(10):
        filled_found = False
        for r in range(20):
            if board[r][c]:
                filled_found = True
            elif filled_found:
                holes += 1
                
    max_height = 0
    for c in range(10):
        height = sum(1 for r in range(20) if board[r][c])
        if height > max_height:
            max_height = height
            
    tops = [20] * 10
    for c in range(10):
        for r in range(20):
            if board[r][c]:
                tops[c] = r
                break
                
    surface_diff = 0
    for c in range(9):
        surface_diff += abs(tops[c] - tops[c+1])
        
    score_val = placement["lines_cleared"] * 100
    score_val += -holes * 50
    score_val += -max_height * 10
    score_val += -surface_diff
    score_val += placement["rotation"] * 0.1
    
    return float(score_val)
