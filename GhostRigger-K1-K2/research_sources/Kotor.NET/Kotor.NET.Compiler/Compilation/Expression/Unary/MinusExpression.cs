using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Unary
{
    public class MinusExpression : IExpression
    {
        public IExpression Expression { get; set; }

        public MinusExpression(IExpression expression)
        {
            Expression = expression;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            Expression.Compile(symbolTable, ncs);

            var type = Expression.GetDataType();

            if (type == DataType.Int)
            {
                ncs.Add(new NCSInstruction.NEGI());
            }
            else if (type == DataType.Float)
            {
                ncs.Add(new NCSInstruction.NEGF());
            }
            else
            {
                throw new NotImplementedException();
            }
        }
    }
}
