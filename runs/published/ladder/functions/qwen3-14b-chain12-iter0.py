def score(board, placement):
    # Calculate column heights
    column_heights = []
    for c in range(10):
        height = 0
        for r in reversed(range(20)):  # from bottom to top
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)
    
    # Calculate max height, aggregate height, holes, and bumpiness
    max_height = max(column_heights)
    aggregate_height = sum(column_heights)
    
    # Calculate number of holes
    holes = sum(max(0, 20 - h) for h in column_heights if h > 0)
    
    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(column_heights[i] - column_heights[i+1])
    
    # Unique term to ensure different placements get different scores
    kind_map = {'I': 0, 'O': 1, 'T': 2, 'S': 3, 'Z': 4, 'J': 5, 'L': 6}
    unique_term = (placement['column'] + placement['row'] + placement['rotation'] + kind_map[placement['kind']]) * 0.0001
    
    # Final score calculation
    lines = placement["lines_cleared"]
    score = (lines * 100) - (max_height * 10) - (holes * 5) - (aggregate_height * 2) - (bumpiness * 1) + unique_term
    return score
