def score(board, placement):
    holes = 0
    for j in range(10):
        filled_found = False
        for i in range(20):
            if board[i][j]:
                filled_found = True
            elif filled_found:
                holes += 1
                
    top_rows = []
    for j in range(10):
        found = False
        for i in range(20):
            if board[i][j]:
                top_rows.append(i)
                found = True
                break
        if not found:
            top_rows.append(20)
            
    avg_top = sum(top_rows) / 10.0
    var = 0.0
    for t in top_rows:
        diff = t - avg_top
        var += diff * diff
        
    base_score = placement["lines_cleared"] * 100
    holes_score = holes * 10
    variance_score = var * 10
    tie_breaker = placement["row"] * 1000.0 + placement["column"] * 10.0
    
    total_score = base_score - holes_score - variance_score + tie_breaker
    return total_score
