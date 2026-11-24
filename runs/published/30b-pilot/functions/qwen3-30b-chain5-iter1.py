def score(board, placement):
    holes = 0
    for j in range(10):
        has_filled = False
        for i in range(20):
            if board[i][j]:
                has_filled = True
            else:
                if has_filled:
                    holes += 1
                    
    top_rows = []
    for j in range(10):
        top = 20
        for i in range(20):
            if board[i][j]:
                top = i
                break
        top_rows.append(top)
        
    min_top = min(top_rows)
    sum_top = sum(top_rows)
    mean = sum_top / 10.0
    variance = sum((x - mean) ** 2 for x in top_rows) / 10.0
    std_dev = math.sqrt(variance)
    
    lines_cleared = placement["lines_cleared"]
    
    score_val = (lines_cleared * 100) + (min_top * 20) - (holes * 30) - (std_dev * 15) + (placement["column"] * 0.1)
    
    return score_val
