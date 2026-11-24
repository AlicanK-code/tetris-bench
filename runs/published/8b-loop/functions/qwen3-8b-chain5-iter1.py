def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        has_filled_above = False
        for r in range(20):
            if board[r][c]:
                has_filled_above = True
            else:
                if has_filled_above:
                    holes += 1
    
    # Calculate max_height
    max_height = 0
    for c in range(10):
        current_height = 0
        for r in range(19, -1, -1):
            if board[r][c]:
                current_height = r
                break
        if current_height > max_height:
            max_height = current_height
    
    # Calculate standard deviation of column heights
    heights = []
    for c in range(10):
        current_height = 0
        for r in range(19, -1, -1):
            if board[r][c]:
                current_height = r
                break
        heights.append(current_height)
    
    mean = sum(heights) / 10
    variance = sum((h - mean)**2 for h in heights) / 10
    std_dev = math.sqrt(variance)
    
    return lines_cleared * 100 - holes - max_height - std_dev
