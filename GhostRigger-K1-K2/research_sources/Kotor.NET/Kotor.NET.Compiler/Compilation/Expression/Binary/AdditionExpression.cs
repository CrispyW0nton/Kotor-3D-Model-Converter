using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Binary
{
    public class AdditionExpression : IExpression
    {
        public IExpression LHS { get; set; }
        public IExpression RHS { get; set; }

        public AdditionExpression(IExpression lhs, IExpression rhs)
        {
            LHS = lhs;
            RHS = rhs;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            LHS.Compile(symbolTable, ncs);
            RHS.Compile(symbolTable, ncs);

            var lhs = LHS.GetDataType();
            var rhs = RHS.GetDataType();

            if (lhs == DataType.Int && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.ADDII());
            }
            else if (lhs == DataType.Int && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.ADDIF());
            }
            else if (lhs == DataType.Float && rhs == DataType.Int)
            {
                ncs.Add(new NCSInstruction.ADDFI());
            }
            else if (lhs == DataType.Float && rhs == DataType.Float)
            {
                ncs.Add(new NCSInstruction.ADDFF());
            }
            else if (lhs == DataType.String && rhs == DataType.String)
            {
                ncs.Add(new NCSInstruction.ADDSS());
            }
            else if (lhs == DataType.Vector && rhs == DataType.Vector)
            {
                ncs.Add(new NCSInstruction.ADDVV());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
