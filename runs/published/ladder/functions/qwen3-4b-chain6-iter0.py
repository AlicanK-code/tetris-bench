def score(board, placement):
    lines = placement["lines_cleared"]
    hole_count = 0
    for j in range(10):
        for i in range(20):
            if not board[i][j]:
                for k in range(i):
                    if board[k][j]:
                        hole_count += 1
                        break
    
    column_heights = [0] * 10
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                column_heights[j] += 1
    
    max_height = max(column_heights)
    mean = sum(column_heights) / 10.0
    variance = sum((h - mean) ** 2 for h in column_heights)
    
    return float(lines * 10 + (200 - hole_count) - max_height * 5 + (100 - variance))
