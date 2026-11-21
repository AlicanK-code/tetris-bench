def score(board, placement):
    # Calculate aggregate height
    aggregate_height = 0
    for column in range(10):
        height = 0
        for row in range(20):
            if board[row][column]:
                height += 1
            else:
                break
        aggregate_height += height

    # Calculate number of holes
    holes = 0
    for column in range(10):
        filled_rows = [row for row in range(20) if board[row][column]]
        for row in range(20):
            if not board[row][column]:
                if any(filled_row > row for filled_row in filled_rows):
                    holes += 1

    # Calculate bumpiness
    column_heights = []
    for column in range(10):
        height = 0
        for row in range(20):
            if board[row][column]:
                height += 1
            else:
                break
        column_heights.append(height)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(column_heights[i] - column_heights[i + 1])

    # Combine all factors with weights
    lines_cleared = placement["lines_cleared"]
    score = (lines_cleared * 100) - (aggregate_height * 1) - (holes * 5) - (bumpiness * 0.5)
    
    # Add a small unique term to ensure different placements have different scores
    score += (placement["column"] + placement["row"] + placement["rotation"] + ord(placement["kind"])) * 0.0001
    
    return float(score)
