def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    holes = 0
    for j in range(10):
        for i in range(1, 20):
            if not board[i][j] and board[i-1][j]:
                holes += 1
                
    sum_top = 0
    for j in range(10):
        top_row = 20
        for i in range(20):
            if board[i][j]:
                top_row = i
                break
        sum_top += top_row
        
    col_term = 10 - abs(placement["column"] - 4)
    col_val = col_term * 100
    
    score_val = (lines_cleared * 1000000) - (holes * 10000) - (sum_top * 100) + col_val
    return score_val
